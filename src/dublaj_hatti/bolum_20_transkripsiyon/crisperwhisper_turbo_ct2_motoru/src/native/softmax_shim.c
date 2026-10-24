#define _GNU_SOURCE
#include <dlfcn.h>
#include <limits.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef void (*compute_fn)(void *, void *, void *, void *);
typedef void *(*data_fn)(void *);
typedef void *(*stream_fn)(void);
typedef int (*launch_fn)(void *, unsigned, unsigned, unsigned, unsigned, unsigned, unsigned, unsigned, void *, void **, void **);
static compute_fn original;
static data_fn input_data, output_data;
static stream_fn get_stream;
static launch_fn launch;
static void *module, *function;
static _Atomic int enabled = 0;
static _Atomic unsigned long changed = 0, fallback = 0;
static int retained_context = 0;
static unsigned thread_cap = 1024;

static void *required(const char *name) {
    void *value = dlsym(RTLD_NEXT, name);
    if (!value) {fprintf(stderr, "Missing softmax shim symbol: %s\n", name); _Exit(70);}
    return value;
}

static void checked(int value) {
    if (value) {fprintf(stderr, "Softmax shim CUDA status: %d\n", value); _Exit(70);}
}

void ct2_softmax_prepare(const char *path) {
    typedef int (*context_get_fn)(void **);
    typedef int (*context_retain_fn)(void **, int);
    typedef int (*context_set_fn)(void *);
    typedef int (*module_load_fn)(void **, const char *);
    typedef int (*function_get_fn)(void **, void *, const char *);
    void *context = NULL;
    checked(((context_get_fn)required("cuCtxGetCurrent"))(&context));
    if (!context) {
        checked(((context_retain_fn)required("cuDevicePrimaryCtxRetain"))(&context, 0));
        checked(((context_set_fn)required("cuCtxSetCurrent"))(context));
        retained_context = 1;
    }
    original = (compute_fn)required("_ZNK11ctranslate23ops7SoftMax7computeILNS_6DeviceE1EfEEvRKNS_11StorageViewEPS5_RS4_");
    input_data = (data_fn)required("_ZNK11ctranslate211StorageView4dataIfEEPKT_v");
    output_data = (data_fn)required("_ZN11ctranslate211StorageView4dataIfEEPT_v");
    get_stream = (stream_fn)required("_ZN11ctranslate24cuda15get_cuda_streamEv");
    launch = (launch_fn)required("cuLaunchKernel");
    checked(((module_load_fn)required("cuModuleLoad"))(&module, path));
    checked(((function_get_fn)required("cuModuleGetFunction"))(&function, module, "softmax_parallel_max"));
    atomic_store(&enabled, 1);
}

void ct2_softmax_select(unsigned variant) {
    typedef int (*function_get_fn)(void **, void *, const char *);
    const char *names[] = {"softmax_parallel_max", "softmax_packed_512", "softmax_packed_256", "softmax_packed_128"};
    const unsigned caps[] = {1024, 512, 256, 128};
    if (variant > 3 || !module) _Exit(70);
    checked(((function_get_fn)required("cuModuleGetFunction"))(&function, module, names[variant]));
    thread_cap = caps[variant];
}

void _ZNK11ctranslate23ops7SoftMax7computeILNS_6DeviceE1EfEEvRKNS_11StorageViewEPS5_RS4_(void *self, void *input, void *lengths, void *output) {
    if (!original) original = (compute_fn)required("_ZNK11ctranslate23ops7SoftMax7computeILNS_6DeviceE1EfEEvRKNS_11StorageViewEPS5_RS4_");
    if (!atomic_load(&enabled) || lengths || *((unsigned char *)self + 8)) {
        atomic_fetch_add(&fallback, 1);
        original(self, input, lengths, output);
        return;
    }
    int64_t size;
    int64_t *shape_end;
    memcpy(&size, (unsigned char *)input + 40, sizeof(size));
    memcpy(&shape_end, (unsigned char *)input + 56, sizeof(shape_end));
    int64_t cols = shape_end[-1];
    if (cols < 1 || cols > 2048 || size < cols || size % cols || size / cols > UINT_MAX) {
        atomic_fetch_add(&fallback, 1);
        original(self, input, lengths, output);
        return;
    }
    unsigned columns = (unsigned)cols;
    unsigned rows = (unsigned)(size / cols);
    unsigned target = columns / 2;
    if (target > 1024) target = 1024;
    unsigned threads = 1;
    while (threads < target) threads *= 2;
    if (threads < 32) threads = 32;
    void *source = input_data(input), *destination = output_data(output);
    void *parameters[] = {&destination, &source, &columns};
    unsigned actual_threads = threads < thread_cap ? threads : thread_cap;
    checked(launch(function, rows, 1, 1, actual_threads, 1, 1, (threads + threads / 32) * 4, get_stream(), parameters, NULL));
    atomic_fetch_add(&changed, 1);
}

unsigned long ct2_softmax_changed(void) {return atomic_load(&changed);}
unsigned long ct2_softmax_fallback(void) {return atomic_load(&fallback);}

void ct2_softmax_close(void) {
    atomic_store(&enabled, 0);
    if (module) {
        typedef int (*module_unload_fn)(void *);
        checked(((module_unload_fn)required("cuModuleUnload"))(module));
        module = NULL;
    }
    if (retained_context) {
        typedef int (*context_release_fn)(int);
        checked(((context_release_fn)required("cuDevicePrimaryCtxRelease_v2"))(0));
        retained_context = 0;
    }
}
