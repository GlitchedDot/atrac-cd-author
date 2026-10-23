/* winewrap: ptrace supervisor that adds MAP_NORESERVE to huge anonymous
 * mmaps anywhere in the traced tree. Wine's preloader reserves ~32 GiB
 * RW in one mmap; this sandbox has 8 GB RAM with overcommit_memory=0
 * (and a read-only /proc), so the reservation fails with ENOMEM and
 * Wine dies. NORESERVE skips the upfront accounting; pages still fault
 * in normally on use. */
#define _GNU_SOURCE
#include <sys/ptrace.h>
#include <sys/wait.h>
#include <sys/user.h>
#include <sys/types.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>

#define MAP_NORESERVE 0x4000
#define MAP_ANONYMOUS 0x20

static int in_syscall[65536];

static void patch_if_huge(pid_t pid)
{
    struct user_regs_struct r;
    if (ptrace(PTRACE_GETREGS, pid, 0, &r) < 0)
        return;
    if (r.orig_rax != 9) /* mmap */
        return;
    if (r.rsi >= (1ULL << 31) && (r.r10 & MAP_ANONYMOUS) && !(r.r10 & MAP_NORESERVE)) {
        r.r10 |= MAP_NORESERVE;
        ptrace(PTRACE_SETREGS, pid, 0, &r);
    }
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "usage: winewrap <program> [args...]\n");
        return 2;
    }
    pid_t child = fork();
    if (child == 0) {
        ptrace(PTRACE_TRACEME, 0, 0, 0);
        raise(SIGSTOP);
        execvp(argv[1], &argv[1]);
        _exit(127);
    }
    int status;
    waitpid(child, &status, 0);
    ptrace(PTRACE_SETOPTIONS, child, 0,
           PTRACE_O_TRACESYSGOOD | PTRACE_O_TRACEFORK | PTRACE_O_TRACEVFORK |
           PTRACE_O_TRACECLONE | PTRACE_O_TRACEEXEC);
    ptrace(PTRACE_SYSCALL, child, 0, 0);

    int main_status = 0;
    pid_t main_pid = child;
    for (;;) {
        pid_t pid = waitpid(-1, &status, __WALL);
        if (pid < 0) {
            if (errno == EINTR)
                continue;
            break; /* no children left */
        }
        if (WIFEXITED(status) || WIFSIGNALED(status)) {
            if (pid == main_pid) {
                main_status = WIFEXITED(status) ? WEXITSTATUS(status)
                                                 : 128 + WTERMSIG(status);
                /* keep draining until no children remain */
                if (waitpid(-1, &status, __WALL | WNOHANG) < 0)
                    break;
            }
            continue;
        }
        int sig = WSTOPSIG(status);
        unsigned long event = (unsigned long)status >> 16;
        if (event != 0) { /* fork/clone/exec event: just continue */
            ptrace(PTRACE_SYSCALL, pid, 0, 0);
            continue;
        }
        if (sig == (SIGTRAP | 0x80)) { /* syscall stop */
            if (!in_syscall[pid & 0xffff]) {
                patch_if_huge(pid);
                in_syscall[pid & 0xffff] = 1;
            } else {
                in_syscall[pid & 0xffff] = 0;
            }
            ptrace(PTRACE_SYSCALL, pid, 0, 0);
            continue;
        }
        /* real signal: reinject */
        ptrace(PTRACE_SYSCALL, pid, 0, sig);
    }
    return main_status;
}
