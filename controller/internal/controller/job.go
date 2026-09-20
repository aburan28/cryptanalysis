package controller

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"sort"

	batchv1 "k8s.io/api/batch/v1"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/utils/ptr"

	"github.com/aburan28/cryptanalysis/controller/api/v1alpha1"
)

const (
	walkerContainer   = "walker"
	spoolVolume       = "spool"
	webIdentityVolume = "aws-web-identity-token"
	webIdentityMount  = "/var/run/secrets/aws/serviceaccount"
	managedBy         = "campaign-controller"
	walkerAppName     = "cryptanalysis-walker"
)

// contractEnv lists the variables the controller owns; user env may not
// override them.
var contractEnv = map[string]struct{}{
	v1alpha1.EnvCurve: {}, v1alpha1.EnvCampaign: {}, v1alpha1.EnvContractID: {},
	v1alpha1.EnvBucket: {}, v1alpha1.EnvAWSRegion: {}, v1alpha1.EnvAWSDefaultReg: {},
	v1alpha1.EnvPublishURL: {}, v1alpha1.EnvPublishToken: {}, v1alpha1.EnvSlotBase: {},
	v1alpha1.EnvSlotCount: {}, v1alpha1.EnvSpoolDir: {}, v1alpha1.EnvCompletionIdx: {},
	v1alpha1.EnvAWSRoleArn: {}, v1alpha1.EnvAWSTokenFile: {}, v1alpha1.EnvAWSSessionName: {},
	v1alpha1.EnvAWSSTSRegional: {},
}

// SlotCount is the size of the Campaign's slot range.
func SlotCount(c *v1alpha1.Campaign) int32 {
	if c.Spec.Workers.SlotCount != nil && *c.Spec.Workers.SlotCount > c.Spec.Workers.Parallelism {
		return *c.Spec.Workers.SlotCount
	}
	return c.Spec.Workers.Parallelism
}

// SpecHash identifies the immutable part of the walker Job: everything except
// parallelism and suspension. A change hands over to a new Job.
func SpecHash(c *v1alpha1.Campaign) string {
	template, _ := podTemplate(c)
	payload := struct {
		Template    corev1.PodTemplateSpec  `json:"template"`
		Completions int32                   `json:"completions"`
		Backoff     *int32                  `json:"backoff"`
		Queue       v1alpha1.SchedulingSpec `json:"queue"`
	}{template, SlotCount(c), c.Spec.Workers.BackoffLimit, c.Spec.Scheduling}
	raw, err := json.Marshal(payload)
	if err != nil {
		panic(fmt.Sprintf("marshal spec hash payload: %v", err))
	}
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:])[:10]
}

// JobName returns the Job name for a Campaign and spec hash.
func JobName(c *v1alpha1.Campaign, hash string) string {
	base := c.Name
	suffix := "-walkers-" + hash
	if len(base)+len(suffix) > 63 {
		base = base[:63-len(suffix)]
	}
	return base + suffix
}

// BuildJob renders the walker Job for the Campaign at the given parallelism.
// It returns the names of user env entries dropped for colliding with the
// walker contract.
func BuildJob(c *v1alpha1.Campaign, parallelism int32) (*batchv1.Job, []string) {
	hash := SpecHash(c)
	template, dropped := podTemplate(c)
	labels := map[string]string{
		"app.kubernetes.io/name":       walkerAppName,
		"app.kubernetes.io/part-of":    "cryptanalysis",
		"app.kubernetes.io/managed-by": managedBy,
		v1alpha1.LabelCampaign:         c.Name,
		v1alpha1.LabelSpecHash:         hash,
		v1alpha1.KueueQueueNameLabel:   c.Spec.Scheduling.QueueName,
	}
	if c.Spec.Scheduling.WorkloadPriorityClass != "" {
		labels[v1alpha1.KueuePriorityClassLabel] = c.Spec.Scheduling.WorkloadPriorityClass
	}
	annotations := map[string]string{}
	if elastic(c) {
		annotations[v1alpha1.KueueElasticJobAnnotation] = "true"
	}
	backoff := c.Spec.Workers.BackoffLimit
	if backoff == nil {
		backoff = ptr.To[int32](1000)
	}
	job := &batchv1.Job{
		ObjectMeta: metav1.ObjectMeta{
			Name:        JobName(c, hash),
			Namespace:   c.Namespace,
			Labels:      labels,
			Annotations: annotations,
		},
		Spec: batchv1.JobSpec{
			// Kueue admits suspended Jobs; it flips suspend itself.
			Suspend:        ptr.To(true),
			Parallelism:    ptr.To(parallelism),
			Completions:    ptr.To(SlotCount(c)),
			CompletionMode: ptr.To(batchv1.IndexedCompletion),
			BackoffLimit:   backoff,
			PodFailurePolicy: &batchv1.PodFailurePolicy{
				Rules: []batchv1.PodFailurePolicyRule{{
					// Preemption, drains and evictions are expected in a
					// quota-managed fleet and must not burn the backoff limit.
					Action: batchv1.PodFailurePolicyActionIgnore,
					OnPodConditions: []batchv1.PodFailurePolicyOnPodConditionsPattern{{
						Type:   corev1.DisruptionTarget,
						Status: corev1.ConditionTrue,
					}},
				}},
			},
			Template: template,
		},
	}
	return job, dropped
}

func elastic(c *v1alpha1.Campaign) bool {
	return c.Spec.Scheduling.Elastic == nil || *c.Spec.Scheduling.Elastic
}

func podTemplate(c *v1alpha1.Campaign) (corev1.PodTemplateSpec, []string) {
	w := c.Spec.Workers
	labels := map[string]string{}
	for k, v := range w.PodLabels {
		labels[k] = v
	}
	labels["app.kubernetes.io/name"] = walkerAppName
	labels["app.kubernetes.io/part-of"] = "cryptanalysis"
	labels["app.kubernetes.io/managed-by"] = managedBy
	labels[v1alpha1.LabelCampaign] = c.Name
	labels[v1alpha1.LabelPublisherClient] = "true"

	spoolPath := w.Spool.MountPath
	if spoolPath == "" {
		spoolPath = "/var/spool/cryptanalysis"
	}
	env := []corev1.EnvVar{
		{Name: v1alpha1.EnvCurve, Value: c.Spec.Target.Curve},
		{Name: v1alpha1.EnvCampaign, Value: c.Spec.Target.CampaignID},
		{Name: v1alpha1.EnvContractID, Value: c.Spec.Target.ContractID},
		{Name: v1alpha1.EnvBucket, Value: c.Spec.Coordinator.Bucket},
		{Name: v1alpha1.EnvAWSRegion, Value: c.Spec.Coordinator.AWSRegion},
		{Name: v1alpha1.EnvAWSDefaultReg, Value: c.Spec.Coordinator.AWSRegion},
		{Name: v1alpha1.EnvPublishURL, Value: c.Spec.Coordinator.PublishURL},
		{Name: v1alpha1.EnvPublishToken, ValueFrom: &corev1.EnvVarSource{
			SecretKeyRef: c.Spec.Coordinator.TokenSecretRef.DeepCopy(),
		}},
		{Name: v1alpha1.EnvSlotBase, Value: fmt.Sprint(w.SlotBase)},
		{Name: v1alpha1.EnvSlotCount, Value: fmt.Sprint(SlotCount(c))},
		{Name: v1alpha1.EnvSpoolDir, Value: spoolPath},
		{Name: "RHO_WORKER_ID", ValueFrom: &corev1.EnvVarSource{
			FieldRef: &corev1.ObjectFieldSelector{FieldPath: "metadata.name"},
		}},
		{Name: "RHO_NODE_NAME", ValueFrom: &corev1.EnvVarSource{
			FieldRef: &corev1.ObjectFieldSelector{FieldPath: "spec.nodeName"},
		}},
	}
	volumes := []corev1.Volume{{
		Name: spoolVolume,
		VolumeSource: corev1.VolumeSource{EmptyDir: &corev1.EmptyDirVolumeSource{
			Medium:    w.Spool.Medium,
			SizeLimit: w.Spool.SizeLimit,
		}},
	}}
	mounts := []corev1.VolumeMount{{Name: spoolVolume, MountPath: spoolPath}}

	if wi := w.WebIdentity; wi != nil {
		audience := wi.Audience
		if audience == "" {
			audience = "sts.amazonaws.com"
		}
		expiry := wi.ExpirationSeconds
		if expiry == 0 {
			expiry = 3600
		}
		volumes = append(volumes, corev1.Volume{
			Name: webIdentityVolume,
			VolumeSource: corev1.VolumeSource{Projected: &corev1.ProjectedVolumeSource{
				Sources: []corev1.VolumeProjection{{
					ServiceAccountToken: &corev1.ServiceAccountTokenProjection{
						Audience:          audience,
						ExpirationSeconds: ptr.To(expiry),
						Path:              "token",
					},
				}},
			}},
		})
		mounts = append(mounts, corev1.VolumeMount{
			Name: webIdentityVolume, MountPath: webIdentityMount, ReadOnly: true,
		})
		env = append(env,
			corev1.EnvVar{Name: v1alpha1.EnvAWSRoleArn, Value: wi.RoleArn},
			corev1.EnvVar{Name: v1alpha1.EnvAWSTokenFile, Value: webIdentityMount + "/token"},
			corev1.EnvVar{Name: v1alpha1.EnvAWSSessionName, Value: sessionName(c)},
			corev1.EnvVar{Name: v1alpha1.EnvAWSSTSRegional, Value: "regional"},
		)
	}

	var dropped []string
	for _, e := range w.Env {
		if _, reserved := contractEnv[e.Name]; reserved {
			dropped = append(dropped, e.Name)
			continue
		}
		env = append(env, e)
	}
	sort.Strings(dropped)

	grace := w.TerminationGracePeriodSeconds
	if grace == nil {
		grace = ptr.To[int64](120)
	}
	return corev1.PodTemplateSpec{
		ObjectMeta: metav1.ObjectMeta{Labels: labels, Annotations: copyMap(w.PodAnnotations)},
		Spec: corev1.PodSpec{
			// OnFailure restarts a crashed walker in place, keeping its index.
			RestartPolicy:                 corev1.RestartPolicyOnFailure,
			ServiceAccountName:            w.ServiceAccountName,
			PriorityClassName:             w.PriorityClassName,
			NodeSelector:                  copyMap(w.NodeSelector),
			Tolerations:                   w.Tolerations,
			Affinity:                      w.Affinity,
			ImagePullSecrets:              w.ImagePullSecrets,
			TerminationGracePeriodSeconds: grace,
			SecurityContext:               w.PodSecurityContext,
			Volumes:                       volumes,
			Containers: []corev1.Container{{
				Name:            walkerContainer,
				Image:           w.Image,
				ImagePullPolicy: w.ImagePullPolicy,
				Command:         w.Command,
				Args:            w.Args,
				Env:             env,
				Resources:       w.Resources,
				VolumeMounts:    mounts,
				SecurityContext: w.SecurityContext,
			}},
		},
	}, dropped
}

func sessionName(c *v1alpha1.Campaign) string {
	name := "campaign-" + c.Namespace + "-" + c.Name
	if len(name) > 64 {
		name = name[:64]
	}
	return name
}

func copyMap(in map[string]string) map[string]string {
	if len(in) == 0 {
		return nil
	}
	out := make(map[string]string, len(in))
	for k, v := range in {
		out[k] = v
	}
	return out
}
