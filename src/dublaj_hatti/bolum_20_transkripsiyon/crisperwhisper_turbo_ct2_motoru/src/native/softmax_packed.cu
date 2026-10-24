#include "softmax_padded.cu"

template<unsigned capacity>
__device__ __forceinline__ void packed_body(float *output, const float *input, unsigned cols) {
    extern __shared__ float shared[];
    input += (unsigned long long)blockIdx.x * cols;
    output += (unsigned long long)blockIdx.x * cols;
    unsigned target = cols / 2;
    if (target > 1024) target = 1024;
    unsigned virtual_threads = 32;
    while (virtual_threads < target) virtual_threads *= 2;
    float values[capacity];
    float maximum = -FLT_MAX;
    #pragma unroll
    for (unsigned j = 0; j < capacity; ++j) {
        unsigned i = threadIdx.x + j * blockDim.x;
        values[j] = i < cols ? input[i] : -FLT_MAX;
        if (i < cols) maximum = fmaxf(maximum, values[j]);
    }
    maximum = parallel_max(maximum, shared);
    #pragma unroll
    for (unsigned j = 0; j < capacity; ++j)
        if (threadIdx.x + j * blockDim.x < cols)
            values[j] = expf(values[j] - maximum);
    __syncthreads();
    unsigned stride = virtual_threads / blockDim.x;
    for (unsigned group = 0; group < stride; ++group) {
        unsigned virtual_tid = threadIdx.x + group * blockDim.x;
        float sum = 0.0f;
        for (unsigned j = group; j < capacity; j += stride)
            if (threadIdx.x + j * blockDim.x < cols) sum += values[j];
        shared[virtual_tid + virtual_tid / 32] = sum;
    }
    __syncthreads();
    unsigned warps = virtual_threads / 32;
    if (threadIdx.x < warps) {
        float result = 0.0f;
        #pragma unroll
        for (unsigned i = 0; i < 32; ++i)
            result += shared[threadIdx.x * 33 + i];
        __syncwarp((unsigned)((1ull << warps) - 1));
        shared[threadIdx.x] = result;
    }
    __syncthreads();
    if (threadIdx.x == 0) {
        float result = 0.0f;
        for (unsigned i = 0; i < warps; ++i) result += shared[i];
        shared[0] = result;
    }
    __syncthreads();
    float sum = shared[0];
    #pragma unroll
    for (unsigned j = 0; j < capacity; ++j) {
        unsigned i = threadIdx.x + j * blockDim.x;
        if (i < cols) output[i] = values[j] / sum;
    }
}

extern "C" __global__ void softmax_packed_512(float *output, const float *input, unsigned cols) {
    packed_body<4>(output, input, cols);
}
extern "C" __global__ void softmax_packed_256(float *output, const float *input, unsigned cols) {
    packed_body<8>(output, input, cols);
}
extern "C" __global__ void softmax_packed_128(float *output, const float *input, unsigned cols) {
    packed_body<16>(output, input, cols);
}
