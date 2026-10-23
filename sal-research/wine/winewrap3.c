/* winewrap2: like winewrap, but fast. The traced child installs a seccomp
 * filter that raises a ptrace event ONLY for mmap syscalls
 * (SECCOMP_RET_TRACE); everything else runs at full speed. The tracer
 * wakes only for mmap, adds MAP_NORESERVE to huge anonymous reservations
 * (Wine's preloader wants ~32 GiB RW; this sandbox's overcommit heuristic
 * refuses it), and continues the process. */
#define _GNU_SOURCE
#include <sys/ptrace.h>
#include <sys/wait.h>
#include <sys/user.h>
#include <sys/types.h>
#include <sys/prctl.h>
#include <linux/seccomp.h>
#include <linux/filter.h>
#include <linux/audit.h>
#include <sys/syscall.h>
#include <signal.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>

#define MAP_NORESERVE 0x4000
#define MAP_ANONYMOUS 0x20

static void install_filter(void)
{
    struct sock_filter filt[] = {
        BPF_STMT(BPF_LD + BPF_W + BPF_ABS, offsetof(struct seccomp_data, nr)),
        BPF_JUMP(BPF_JMP + BPF_JEQ + BPF_K, __NR_mmap, 0, 1),
        BPF_STMT(BPF_RET + BPF_K, SECCOMP_RET_TRACE | 0x1),
        BPF_STMT(BPF_RET + BPF_K, SECCOMP_RET_ALLOW),
    };
    struct sock_fprog prog = { .len = 4, .filter = filt };
    prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0);
    syscall(__NR_seccomp, SECCOMP_SET_MODE_FILTER, 0, &prog);
}

static int nopatch;
static void patch_if_huge(pid_t pid)
{
    struct user_regs_struct r;
    if (nopatch)
        return;
    if (ptrace(PTRACE_GETREGS, pid, 0, &r) < 0)
        return;
    if (r.orig_rax != __NR_mmap)
        return;
    if (r.rsi >= (1ULL << 31) && (r.r10 & MAP_ANONYMOUS) && !(r.r10 & MAP_NORESERVE)) {
        if (getenv("WINEWRAP_CAP")) {
            r.rsi = (6ULL << 30); /* cap size, keep flags: real backing */
        } else {
            r.r10 |= MAP_NORESERVE;
        }
        ptrace(PTRACE_SETREGS, pid, 0, &r);
    }
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "usage: winewrap2 <program> [args...]\n");
        return 2;
    }
    nopatch = getenv("WINEWRAP_NOPATCH") != NULL;
    pid_t child = fork();
    if (child == 0) {
        ptrace(PTRACE_TRACEME, 0, 0, 0);
        install_filter();
        raise(SIGSTOP);
        execvp(argv[1], &argv[1]);
        _exit(127);
    }
    int status;
    waitpid(child, &status, 0);
    ptrace(PTRACE_SETOPTIONS, child, 0,
           PTRACE_O_TRACESECCOMP | PTRACE_O_TRACEFORK | PTRACE_O_TRACEVFORK |
           PTRACE_O_TRACECLONE | PTRACE_O_TRACEEXEC);
    ptrace(PTRACE_CONT, child, 0, 0);

    int main_status = 0;
    pid_t main_pid = child;
    int main_done = 0;
    for (;;) {
        pid_t pid = waitpid(-1, &status, __WALL);
        if (pid < 0) {
            if (errno == EINTR)
                continue;
            break;
        }
        if (WIFEXITED(status) || WIFSIGNALED(status)) {
            if (pid == main_pid) {
                main_status = WIFEXITED(status) ? WEXITSTATUS(status)
                                                 : 128 + WTERMSIG(status);
                main_done = 1;
            }
            continue;
        }
        int sig = WSTOPSIG(status);
        unsigned long event = (unsigned long)status >> 16;
        if (event == PTRACE_EVENT_SECCOMP) {
            patch_if_huge(pid);
            ptrace(PTRACE_CONT, pid, 0, 0);
            continue;
        }
        if (event != 0) { /* fork/clone/exec */
            ptrace(PTRACE_CONT, pid, 0, 0);
            continue;
        }
        if (sig == SIGTRAP || sig == SIGSTOP) {
            ptrace(PTRACE_CONT, pid, 0, 0);
            continue;
        }
        ptrace(PTRACE_CONT, pid, 0, sig); /* reinject real signals */
        (void)main_done;
    }
    return main_status;
}
