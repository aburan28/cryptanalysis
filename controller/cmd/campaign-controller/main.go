// Command campaign-controller reconciles cryptanalysis.io Campaigns into
// Kueue-scheduled walker Jobs.
package main

import (
	"flag"
	"os"
	"time"

	"k8s.io/apimachinery/pkg/runtime"
	clientgoscheme "k8s.io/client-go/kubernetes/scheme"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/cache"
	"sigs.k8s.io/controller-runtime/pkg/healthz"
	"sigs.k8s.io/controller-runtime/pkg/log/zap"
	metricsserver "sigs.k8s.io/controller-runtime/pkg/metrics/server"

	"github.com/aburan28/cryptanalysis/controller/api/v1alpha1"
	"github.com/aburan28/cryptanalysis/controller/internal/controller"
)

func main() {
	var (
		metricsAddr    string
		probeAddr      string
		leaderElection bool
		namespace      string
		feedTimeout    time.Duration
	)
	flag.StringVar(&metricsAddr, "metrics-bind-address", ":8080", "metrics endpoint; 0 disables")
	flag.StringVar(&probeAddr, "health-probe-bind-address", ":8081", "health probe endpoint")
	flag.BoolVar(&leaderElection, "leader-elect", false, "enable leader election")
	flag.StringVar(&namespace, "namespace", "", "restrict watches to one namespace; empty watches all")
	flag.DurationVar(&feedTimeout, "status-feed-timeout", 10*time.Second, "HTTP timeout for the coordinator status feed")
	opts := zap.Options{Development: false}
	opts.BindFlags(flag.CommandLine)
	flag.Parse()

	ctrl.SetLogger(zap.New(zap.UseFlagOptions(&opts)))
	setupLog := ctrl.Log.WithName("setup")

	scheme := runtime.NewScheme()
	if err := clientgoscheme.AddToScheme(scheme); err != nil {
		setupLog.Error(err, "register client-go scheme")
		os.Exit(1)
	}
	if err := v1alpha1.AddToScheme(scheme); err != nil {
		setupLog.Error(err, "register cryptanalysis.io scheme")
		os.Exit(1)
	}

	options := ctrl.Options{
		Scheme:                 scheme,
		Metrics:                metricsserver.Options{BindAddress: metricsAddr},
		HealthProbeBindAddress: probeAddr,
		LeaderElection:         leaderElection,
		LeaderElectionID:       "campaign-controller.cryptanalysis.io",
	}
	if namespace != "" {
		options.Cache = cache.Options{DefaultNamespaces: map[string]cache.Config{namespace: {}}}
	}
	mgr, err := ctrl.NewManager(ctrl.GetConfigOrDie(), options)
	if err != nil {
		setupLog.Error(err, "create manager")
		os.Exit(1)
	}

	reconciler := &controller.CampaignReconciler{
		Client:   mgr.GetClient(),
		Scheme:   mgr.GetScheme(),
		Recorder: mgr.GetEventRecorderFor("campaign-controller"),
		Feed:     controller.NewHTTPFeedSource(feedTimeout),
	}
	if err := reconciler.SetupWithManager(mgr); err != nil {
		setupLog.Error(err, "create controller")
		os.Exit(1)
	}
	if err := mgr.AddHealthzCheck("healthz", healthz.Ping); err != nil {
		setupLog.Error(err, "add healthz")
		os.Exit(1)
	}
	if err := mgr.AddReadyzCheck("readyz", healthz.Ping); err != nil {
		setupLog.Error(err, "add readyz")
		os.Exit(1)
	}

	setupLog.Info("starting campaign controller")
	if err := mgr.Start(ctrl.SetupSignalHandler()); err != nil {
		setupLog.Error(err, "manager exited")
		os.Exit(1)
	}
}
