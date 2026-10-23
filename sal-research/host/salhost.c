/* salhost.c — minimal host for Sony's salwrap.dll under Wine.
 *
 * Loads salwrap.dll, calls the internal get-or-create manager
 * function (RVA 0x1D680, FUN_6511d680) which primes the SAL engine:
 * allocates the arenas and loads init.ocm + region.ocm through the
 * gatekeeper. Then dumps every committed memory region of the
 * process to dump/ for offline analysis (the formed images of the
 * loaded modules should be sitting in the arenas, decoded).
 *
 * Build (Ubuntu terminal): i686-w64-mingw32-gcc -o salhost.exe salhost.c
 */
#include <windows.h>
#include <stdio.h>

typedef void *(__cdecl *GetterFn)(void);
typedef void *(__cdecl *GetMgrFn)(void);

static void dump_memory(void)
{
    SYSTEM_INFO si;
    GetSystemInfo(&si);
    unsigned char *addr = (unsigned char *)si.lpMinimumApplicationAddress;
    unsigned char *maxaddr = (unsigned char *)si.lpMaximumApplicationAddress;
    CreateDirectoryA("dump", NULL);
    FILE *idx = fopen("dump/index.txt", "w");
    int n = 0;
    while (addr < maxaddr) {
        MEMORY_BASIC_INFORMATION mbi;
        if (VirtualQuery(addr, &mbi, sizeof(mbi)) == 0)
            break;
        if (mbi.State == MEM_COMMIT &&
            (mbi.Protect & (PAGE_READONLY | PAGE_READWRITE |
                            PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE |
                            PAGE_WRITECOPY | PAGE_EXECUTE_WRITECOPY))) {
            char path[128];
            snprintf(path, sizeof(path), "dump/%08lx.bin",
                     (unsigned long)(size_t)mbi.BaseAddress);
            FILE *f = fopen(path, "wb");
            if (f) {
                fwrite(mbi.BaseAddress, 1, mbi.RegionSize, f);
                fclose(f);
                if (idx)
                    fprintf(idx, "%08lx %08lx protect=%lx type=%lx\n",
                            (unsigned long)(size_t)mbi.BaseAddress,
                            (unsigned long)mbi.RegionSize,
                            (unsigned long)mbi.Protect,
                            (unsigned long)mbi.Type);
                n++;
            }
        }
        addr = (unsigned char *)mbi.BaseAddress + mbi.RegionSize;
    }
    if (idx)
        fclose(idx);
    printf("dumped %d regions\n", n);
    fflush(stdout);
}

int main(void)
{
    setvbuf(stdout, NULL, _IONBF, 0);
    printf("salhost: starting, loading salwrap.dll\n");
    HMODULE h = LoadLibraryA("salwrap.dll");
    if (!h) {
        printf("LoadLibrary(salwrap.dll) failed: %lu\n",
               (unsigned long)GetLastError());
        fflush(stdout);
        return 1;
    }
    printf("salwrap base: %p\n", (void *)h);
    GetterFn g0 = (GetterFn)GetProcAddress(h, "salwrap0");
    GetterFn g1 = (GetterFn)GetProcAddress(h, "salwrap1");
    GetterFn g2 = (GetterFn)GetProcAddress(h, "salwrap2");
    printf("getters: salwrap0()->%p salwrap1()->%p salwrap2()->%p\n",
           g0 ? g0() : 0, g1 ? g1() : 0, g2 ? g2() : 0);
    if (g1)
        printf("  *salwrap1() = %p (services table)\n",
               *(void **)g1());
    if (g2)
        printf("  *salwrap2() = %p (client table)\n",
               *(void **)g2());
    fflush(stdout);

    GetMgrFn getMgr = (GetMgrFn)((char *)h + 0x1D680);
    printf("calling get-manager (FUN_6511d680)...\n");
    fflush(stdout);
    void *ctx = getMgr();
    printf("manager ctx: %p\n", ctx);
    fflush(stdout);

    dump_memory();
    printf("done\n");
    fflush(stdout);
    return 0;
}
