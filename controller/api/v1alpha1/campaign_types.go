package v1alpha1

import (
	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// Label and annotation keys shared with the coordinator Helm chart and Kueue.
const (
	// LabelCampaign marks every object the controller creates for a Campaign.
	LabelCampaign = "cryptanalysis.io/campaign"
	// LabelPublisherClient is the selector the coordinator NetworkPolicy
	// accepts publisher traffic from.
	LabelPublisherClient = "cryptanalysis.io/ecc2k130-publisher-client"
	// LabelSpecHash records which immutable worker specification a Job
	// realises, so spec changes hand over to a new Job.
	LabelSpecHash = "cryptanalysis.io/spec-hash"

	// KueueQueueNameLabel selects the Kueue LocalQueue.
	KueueQueueNameLabel = "kueue.x-k8s.io/queue-name"
	// KueuePriorityClassLabel selects a Kueue WorkloadPriorityClass.
	KueuePriorityClassLabel = "kueue.x-k8s.io/priority-class"
	// KueueElasticJobAnnotation opts a Job into in-place parallelism changes.
	KueueElasticJobAnnotation = "kueue.x-k8s.io/elastic-job"

	// MaxSlot mirrors the coordinator schema constraint slot BETWEEN 0 AND 65534.
	MaxSlot = 65534
)

// Environment variables that form the walker contract.
const (
	EnvCurve          = "RHO_CURVE"
	EnvCampaign       = "RHO_CAMPAIGN"
	EnvContractID     = "ECC2K130_CAMPAIGN_ID"
	EnvBucket         = "ECC_BUCKET"
	EnvAWSRegion      = "AWS_REGION"
	EnvAWSDefaultReg  = "AWS_DEFAULT_REGION"
	EnvPublishURL     = "RHO_QUEUE_PUBLISH_URL"
	EnvPublishToken   = "RHO_QUEUE_PUBLISH_TOKEN"
	EnvSlotBase       = "RHO_SLOT_BASE"
	EnvSlotCount      = "RHO_SLOT_COUNT"
	EnvSpoolDir       = "RHO_SPOOL_DIR"
	EnvCompletionIdx  = "JOB_COMPLETION_INDEX"
	EnvAWSRoleArn     = "AWS_ROLE_ARN"
	EnvAWSTokenFile   = "AWS_WEB_IDENTITY_TOKEN_FILE"
	EnvAWSSessionName = "AWS_ROLE_SESSION_NAME"
	EnvAWSSTSRegional = "AWS_STS_REGIONAL_ENDPOINTS"
)

// CampaignSpec describes a distributed Pollard rho campaign and how its
// walkers are scheduled.
type CampaignSpec struct {
	// Target identifies what is being attacked and under which contract.
	Target TargetSpec `json:"target"`

	// Coordinator is the S3/Redis/RDS coordinator the walkers publish to.
	Coordinator CoordinatorSpec `json:"coordinator"`

	// Workers describes the walker container and its desired parallelism.
	Workers WorkerSpec `json:"workers"`

	// Scheduling places the walker Job on a Kueue queue.
	Scheduling SchedulingSpec `json:"scheduling"`

	// Backpressure scales walkers with the coordinator's queue pressure when
	// coordinator.statusURL is set.
	// +optional
	Backpressure *BackpressureSpec `json:"backpressure,omitempty"`

	// OnCollision selects what happens once the coordinator records a
	// collision. Continue keeps walking because a collision is not a verified
	// discrete logarithm; Suspend releases the walkers.
	// +kubebuilder:validation:Enum=Continue;Suspend
	// +kubebuilder:default=Continue
	// +optional
	OnCollision CollisionPolicy `json:"onCollision,omitempty"`

	// Suspend deletes the walker Job and releases its quota. Campaign state
	// lives in S3 checkpoints, so this is safe and reversible.
	// +optional
	Suspend bool `json:"suspend,omitempty"`
}

// CollisionPolicy is the action taken when a collision is recorded.
type CollisionPolicy string

const (
	// CollisionContinue keeps the walkers running.
	CollisionContinue CollisionPolicy = "Continue"
	// CollisionSuspend deletes the walker Job.
	CollisionSuspend CollisionPolicy = "Suspend"
)

// TargetSpec identifies the cryptanalytic target.
type TargetSpec struct {
	// Curve is the public curve identifier, for example certicom-ecc2k-130.
	// +kubebuilder:validation:Pattern=`^[a-z0-9][a-z0-9-]{0,62}$`
	Curve string `json:"curve"`

	// CampaignID is the coordinator campaign name (RHO_CAMPAIGN).
	// +kubebuilder:validation:Pattern=`^[a-z0-9][a-z0-9-]{0,62}$`
	CampaignID string `json:"campaignId"`

	// ContractID is the strict campaign contract hash (ECC2K130_CAMPAIGN_ID).
	// +kubebuilder:validation:Pattern=`^(|[0-9a-f]{64})$`
	// +optional
	ContractID string `json:"contractId,omitempty"`
}

// CoordinatorSpec locates the coordinator publisher and corpus.
type CoordinatorSpec struct {
	// PublishURL is the publisher API base URL (RHO_QUEUE_PUBLISH_URL).
	// +kubebuilder:validation:Pattern=`^https?://[^\s/]+(/.*)?$`
	PublishURL string `json:"publishURL"`

	// TokenSecretRef names the Secret key holding the publisher bearer token.
	// The Secret must exist in every cluster that runs walkers.
	TokenSecretRef corev1.SecretKeySelector `json:"tokenSecretRef"`

	// Bucket is the campaign S3 bucket walkers upload to (ECC_BUCKET).
	// +kubebuilder:validation:MinLength=3
	Bucket string `json:"bucket"`

	// AWSRegion is the region of the bucket.
	// +kubebuilder:validation:MinLength=1
	AWSRegion string `json:"awsRegion"`

	// StatusURL is the public status.json feed published by the consumer.
	// When set, the controller reads queue pressure and collisions from it.
	// +kubebuilder:validation:Pattern=`^https?://[^\s/]+(/.*)?$`
	// +optional
	StatusURL string `json:"statusURL,omitempty"`
}

// WorkerSpec describes the walker container.
type WorkerSpec struct {
	// Image is the walker container image.
	// +kubebuilder:validation:MinLength=1
	Image string `json:"image"`

	// +optional
	ImagePullPolicy corev1.PullPolicy `json:"imagePullPolicy,omitempty"`

	// +optional
	ImagePullSecrets []corev1.LocalObjectReference `json:"imagePullSecrets,omitempty"`

	// +optional
	Command []string `json:"command,omitempty"`

	// +optional
	Args []string `json:"args,omitempty"`

	// Parallelism is the desired number of concurrent walkers. It may change
	// at any time; Kueue elastic jobs apply it in place.
	// +kubebuilder:validation:Minimum=1
	// +kubebuilder:validation:Maximum=65535
	Parallelism int32 `json:"parallelism"`

	// SlotCount is the size of the slot range this Campaign owns and becomes
	// the Job's completions. Each walker owns slot slotBase +
	// JOB_COMPLETION_INDEX. Defaults to parallelism; raising it later hands
	// over to a new Job because completions are immutable.
	// +kubebuilder:validation:Minimum=1
	// +kubebuilder:validation:Maximum=65535
	// +optional
	SlotCount *int32 `json:"slotCount,omitempty"`

	// SlotBase is the first slot this Campaign owns.
	// +kubebuilder:validation:Minimum=0
	// +kubebuilder:validation:Maximum=65534
	// +kubebuilder:default=0
	// +optional
	SlotBase int32 `json:"slotBase,omitempty"`

	// Resources should request the GPU, for example nvidia.com/gpu: 1.
	// +optional
	Resources corev1.ResourceRequirements `json:"resources,omitempty"`

	// Env is appended after the contract variables and may not override them.
	// +optional
	Env []corev1.EnvVar `json:"env,omitempty"`

	// ServiceAccountName carries the walkers' cloud identity for S3 uploads,
	// for example an IRSA-annotated account.
	// +optional
	ServiceAccountName string `json:"serviceAccountName,omitempty"`

	// WebIdentity mounts a projected token and AWS_* environment so walkers on
	// non-EKS clusters can assume an AWS role for S3 uploads.
	// +optional
	WebIdentity *WebIdentitySpec `json:"webIdentity,omitempty"`

	// Spool is the local directory walkers retain unpublished objects in
	// while the coordinator reports red.
	// +optional
	Spool SpoolSpec `json:"spool,omitempty"`

	// +optional
	NodeSelector map[string]string `json:"nodeSelector,omitempty"`

	// +optional
	Tolerations []corev1.Toleration `json:"tolerations,omitempty"`

	// +optional
	Affinity *corev1.Affinity `json:"affinity,omitempty"`

	// PriorityClassName is the pod priority class, distinct from the Kueue
	// workload priority class.
	// +optional
	PriorityClassName string `json:"priorityClassName,omitempty"`

	// PodLabels are added to walker pods. Kueue Topology Aware Scheduling and
	// similar annotations belong in PodAnnotations.
	// +optional
	PodLabels map[string]string `json:"podLabels,omitempty"`

	// +optional
	PodAnnotations map[string]string `json:"podAnnotations,omitempty"`

	// TerminationGracePeriodSeconds gives walkers time to checkpoint.
	// +kubebuilder:validation:Minimum=0
	// +kubebuilder:default=120
	// +optional
	TerminationGracePeriodSeconds *int64 `json:"terminationGracePeriodSeconds,omitempty"`

	// BackoffLimit bounds pod failures before the Job fails. Disruptions such
	// as preemption never count.
	// +kubebuilder:validation:Minimum=0
	// +kubebuilder:default=1000
	// +optional
	BackoffLimit *int32 `json:"backoffLimit,omitempty"`

	// +optional
	PodSecurityContext *corev1.PodSecurityContext `json:"podSecurityContext,omitempty"`

	// +optional
	SecurityContext *corev1.SecurityContext `json:"securityContext,omitempty"`
}

// WebIdentitySpec federates the walker's Kubernetes identity into AWS IAM.
type WebIdentitySpec struct {
	// RoleArn is assumed through sts:AssumeRoleWithWebIdentity.
	// +kubebuilder:validation:Pattern=`^arn:aws[a-zA-Z-]*:iam::[0-9]{12}:role/[A-Za-z0-9+=,.@_/-]+$`
	RoleArn string `json:"roleArn"`

	// Audience of the projected token; must match the IAM identity provider.
	// +kubebuilder:default="sts.amazonaws.com"
	// +optional
	Audience string `json:"audience,omitempty"`

	// +kubebuilder:validation:Minimum=600
	// +kubebuilder:validation:Maximum=86400
	// +kubebuilder:default=3600
	// +optional
	ExpirationSeconds int64 `json:"expirationSeconds,omitempty"`
}

// SpoolSpec configures the walker spool volume.
type SpoolSpec struct {
	// +kubebuilder:validation:Pattern=`^/[^\s]+$`
	// +kubebuilder:default="/var/spool/cryptanalysis"
	// +optional
	MountPath string `json:"mountPath,omitempty"`

	// SizeLimit caps the emptyDir; walkers that exceed it are evicted rather
	// than filling the node.
	// +optional
	SizeLimit *resource.Quantity `json:"sizeLimit,omitempty"`

	// +optional
	Medium corev1.StorageMedium `json:"medium,omitempty"`
}

// SchedulingSpec binds the walker Job to Kueue.
type SchedulingSpec struct {
	// QueueName is the Kueue LocalQueue in the Campaign's namespace. With a
	// MultiKueue ClusterQueue the Job is dispatched to worker clusters.
	// +kubebuilder:validation:Pattern=`^[a-z0-9]([-a-z0-9]*[a-z0-9])?$`
	QueueName string `json:"queueName"`

	// WorkloadPriorityClass is a Kueue WorkloadPriorityClass name.
	// +optional
	WorkloadPriorityClass string `json:"workloadPriorityClass,omitempty"`

	// Elastic lets the controller resize an admitted Job in place through
	// Kueue workload slices (ElasticJobsViaWorkloadSlices). When false the
	// controller recreates the Job to change parallelism.
	// +kubebuilder:default=true
	// +optional
	Elastic *bool `json:"elastic,omitempty"`
}

// BackpressureSpec maps coordinator queue pressure to walker parallelism.
type BackpressureSpec struct {
	// +kubebuilder:validation:Minimum=10
	// +kubebuilder:default=60
	// +optional
	PollIntervalSeconds int32 `json:"pollIntervalSeconds,omitempty"`

	// RedParallelism is held while the coordinator reports red. Zero deletes
	// the Job so its quota is released.
	// +kubebuilder:validation:Minimum=0
	// +kubebuilder:default=0
	// +optional
	RedParallelism int32 `json:"redParallelism,omitempty"`

	// YellowParallelism is held while the coordinator reports yellow.
	// Defaults to the desired parallelism.
	// +kubebuilder:validation:Minimum=0
	// +optional
	YellowParallelism *int32 `json:"yellowParallelism,omitempty"`

	// RecoverySeconds is how long the feed must stay out of red before
	// parallelism is restored, preventing oscillation.
	// +kubebuilder:validation:Minimum=0
	// +kubebuilder:default=300
	// +optional
	RecoverySeconds int32 `json:"recoverySeconds,omitempty"`

	// StaleAfterSeconds marks the feed stale when generated_at is older than
	// this; a stale feed holds the current parallelism rather than scaling.
	// +kubebuilder:validation:Minimum=60
	// +kubebuilder:default=900
	// +optional
	StaleAfterSeconds int32 `json:"staleAfterSeconds,omitempty"`
}

// CampaignPhase summarises the Campaign for kubectl output.
type CampaignPhase string

const (
	// PhasePending means no Job exists yet.
	PhasePending CampaignPhase = "Pending"
	// PhaseQueued means the Job exists and awaits Kueue admission.
	PhaseQueued CampaignPhase = "Queued"
	// PhaseRunning means the Job is admitted.
	PhaseRunning CampaignPhase = "Running"
	// PhaseBackpressured means the coordinator reduced the effective parallelism.
	PhaseBackpressured CampaignPhase = "Backpressured"
	// PhaseSuspended means spec.suspend or the collision policy released the Job.
	PhaseSuspended CampaignPhase = "Suspended"
	// PhaseFailed means the Job exhausted its backoff limit.
	PhaseFailed CampaignPhase = "Failed"
)

// Condition types reported in CampaignStatus.
const (
	// ConditionAdmitted is true once Kueue unsuspends the Job.
	ConditionAdmitted = "Admitted"
	// ConditionWorkersReady is true when every effective walker is ready.
	ConditionWorkersReady = "WorkersReady"
	// ConditionBackpressured is true while effective parallelism is below desired.
	ConditionBackpressured = "Backpressured"
	// ConditionStatusFresh is true while the coordinator feed is current.
	ConditionStatusFresh = "StatusFresh"
	// ConditionCollisionRecorded is true once the coordinator reports a collision.
	ConditionCollisionRecorded = "CollisionRecorded"
)

// CampaignStatus is the observed state of a Campaign.
type CampaignStatus struct {
	// +optional
	ObservedGeneration int64 `json:"observedGeneration,omitempty"`

	// +optional
	Phase CampaignPhase `json:"phase,omitempty"`

	// JobName is the walker Job currently realising the spec.
	// +optional
	JobName string `json:"jobName,omitempty"`

	// +optional
	DesiredParallelism int32 `json:"desiredParallelism,omitempty"`

	// EffectiveParallelism is what the Job is asked to run after backpressure.
	// +optional
	EffectiveParallelism int32 `json:"effectiveParallelism,omitempty"`

	// +optional
	ActiveWorkers int32 `json:"activeWorkers,omitempty"`

	// +optional
	ReadyWorkers int32 `json:"readyWorkers,omitempty"`

	// QueueState is the coordinator queue pressure: green, yellow, red or unknown.
	// +optional
	QueueState string `json:"queueState,omitempty"`

	// +optional
	QueueMessages int64 `json:"queueMessages,omitempty"`

	// CoordinatorState mirrors status.json state.
	// +optional
	CoordinatorState string `json:"coordinatorState,omitempty"`

	// +optional
	Collisions int64 `json:"collisions,omitempty"`

	// +optional
	DistinguishedPoints int64 `json:"distinguishedPoints,omitempty"`

	// +optional
	LastStatusPoll *metav1.Time `json:"lastStatusPoll,omitempty"`

	// LastRedObserved drives the recovery hysteresis.
	// +optional
	LastRedObserved *metav1.Time `json:"lastRedObserved,omitempty"`

	// +optional
	// +listType=map
	// +listMapKey=type
	// +patchStrategy=merge
	// +patchMergeKey=type
	Conditions []metav1.Condition `json:"conditions,omitempty" patchStrategy:"merge" patchMergeKey:"type"`
}

// Campaign is a distributed cryptanalysis campaign scheduled through Kueue.
//
// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
// +kubebuilder:resource:shortName=camp,categories=cryptanalysis
// +kubebuilder:printcolumn:name="Phase",type=string,JSONPath=`.status.phase`
// +kubebuilder:printcolumn:name="Queue",type=string,JSONPath=`.spec.scheduling.queueName`
// +kubebuilder:printcolumn:name="Desired",type=integer,JSONPath=`.spec.workers.parallelism`
// +kubebuilder:printcolumn:name="Effective",type=integer,JSONPath=`.status.effectiveParallelism`
// +kubebuilder:printcolumn:name="Ready",type=integer,JSONPath=`.status.readyWorkers`
// +kubebuilder:printcolumn:name="Pressure",type=string,JSONPath=`.status.queueState`
// +kubebuilder:printcolumn:name="Collisions",type=integer,JSONPath=`.status.collisions`
// +kubebuilder:printcolumn:name="Age",type=date,JSONPath=`.metadata.creationTimestamp`
// +kubebuilder:validation:XValidation:rule="self.spec.workers.slotBase + self.spec.workers.parallelism <= 65535",message="slotBase + parallelism must not exceed 65535"
// +kubebuilder:validation:XValidation:rule="!has(self.spec.workers.slotCount) || self.spec.workers.slotBase + self.spec.workers.slotCount <= 65535",message="slotBase + slotCount must not exceed 65535"
// +kubebuilder:validation:XValidation:rule="!has(self.spec.workers.slotCount) || self.spec.workers.slotCount >= self.spec.workers.parallelism",message="workers.slotCount must be at least workers.parallelism"
// +kubebuilder:validation:XValidation:rule="!has(self.spec.backpressure) || self.spec.backpressure.redParallelism <= self.spec.workers.parallelism",message="backpressure.redParallelism must not exceed workers.parallelism"
// +kubebuilder:validation:XValidation:rule="!has(self.spec.backpressure) || !has(self.spec.backpressure.yellowParallelism) || self.spec.backpressure.yellowParallelism <= self.spec.workers.parallelism",message="backpressure.yellowParallelism must not exceed workers.parallelism"
// +kubebuilder:validation:XValidation:rule="!has(self.spec.backpressure) || has(self.spec.coordinator.statusURL)",message="backpressure requires coordinator.statusURL"
type Campaign struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec CampaignSpec `json:"spec"`
	// +optional
	Status CampaignStatus `json:"status,omitempty"`
}

// CampaignList contains a list of Campaign.
//
// +kubebuilder:object:root=true
type CampaignList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []Campaign `json:"items"`
}

func init() {
	SchemeBuilder.Register(&Campaign{}, &CampaignList{})
}
