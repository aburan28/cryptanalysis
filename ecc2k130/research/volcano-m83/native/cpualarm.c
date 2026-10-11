// CPU-time caps for Sage solver stages.  An ITIMER_PROF expiry is forwarded
// to the thread that armed it as SIGALRM, which cysignals turns into
// AlarmInterrupt exactly as for its own wall-clock alarm().  Caps therefore
// measure the process's CPU time, not machine load.
#include <pthread.h>
#include <signal.h>
#include <string.h>
#include <sys/time.h>

static pthread_t armed_by;

static void on_prof(int sig)
{
    (void)sig;
    pthread_kill(armed_by, SIGALRM);
}

int cpu_alarm(double seconds)
{
    struct sigaction sa;
    memset(&sa, 0, sizeof sa);
    sa.sa_handler = on_prof;
    sigemptyset(&sa.sa_mask);
    sigaction(SIGPROF, &sa, 0);
    armed_by = pthread_self();
    struct itimerval it;
    memset(&it, 0, sizeof it);
    it.it_value.tv_sec = (long)seconds;
    it.it_value.tv_usec = (long)((seconds - (long)seconds) * 1e6);
    return setitimer(ITIMER_PROF, &it, 0);
}

int cpu_alarm_cancel(void)
{
    struct itimerval it;
    memset(&it, 0, sizeof it);
    return setitimer(ITIMER_PROF, &it, 0);
}
