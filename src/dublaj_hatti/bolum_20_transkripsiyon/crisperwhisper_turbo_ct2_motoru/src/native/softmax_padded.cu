/* Adapted reduction structure from OpenNMT/CTranslate2 v4.7.1 and its attributed PyTorch SoftMax helpers. Original source and licenses: ../references/upstream_softmax/. */
/*
  From PyTorch:

  Copyright (c) 2016-     Facebook, Inc            (Adam Paszke)
  Copyright (c) 2014-     Facebook, Inc            (Soumith Chintala)
  Copyright (c) 2011-2014 Idiap Research Institute (Ronan Collobert)
  Copyright (c) 2012-2014 Deepmind Technologies    (Koray Kavukcuoglu)
  Copyright (c) 2011-2012 NEC Laboratories America (Koray Kavukcuoglu)
  Copyright (c) 2011-2013 NYU                      (Clement Farabet)
  Copyright (c) 2006-2010 NEC Laboratories America (Ronan Collobert, Leon Bottou, Iain Melvin, Jason Weston)
  Copyright (c) 2006      Idiap Research Institute (Samy Bengio)
  Copyright (c) 2001-2004 Idiap Research Institute (Ronan Collobert, Samy Bengio, Johnny Mariethoz)

  From Caffe2:

  Copyright (c) 2016-present, Facebook Inc. All rights reserved.

  All contributions by Facebook:
  Copyright (c) 2016 Facebook Inc.

  All contributions by Google:
  Copyright (c) 2015 Google Inc.
  All rights reserved.

  All contributions by Yangqing Jia:
  Copyright (c) 2015 Yangqing Jia
  All rights reserved.

  All contributions from Caffe:
  Copyright(c) 2013, 2014, 2015, the respective contributors
  All rights reserved.

  All other contributions:
  Copyright(c) 2015, 2016 the respective contributors
  All rights reserved.

  Caffe2 uses a copyright model similar to Caffe: each contributor holds
  copyright over their contributions to Caffe2. The project versioning records
  all such contribution and copyright details. If a contributor wants to further
  mark their specific copyright on a particular contribution, they should
  indicate their copyright solely in the commit message of the change when it is
  committed.

  All rights reserved.

  Redistribution and use in source and binary forms, with or without
  modification, are permitted provided that the following conditions are met:

  1. Redistributions of source code must retain the above copyright
     notice, this list of conditions and the following disclaimer.

  2. Redistributions in binary form must reproduce the above copyright
     notice, this list of conditions and the following disclaimer in the
     documentation and/or other materials provided with the distribution.

  3. Neither the names of Facebook, Deepmind Technologies, NYU, NEC Laboratories America
     and IDIAP Research Institute nor the names of its contributors may be
     used to endorse or promote products derived from this software without
     specific prior written permission.

  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
  ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
  LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
  CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
  SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
  INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
  CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
  ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
  POSSIBILITY OF SUCH DAMAGE.
*/
#include <cuda_runtime.h>
#include <float.h>

template<bool padded, bool addition>
__device__ __forceinline__ float ordered_reduce(float value, float *shared) {
    __syncthreads();
    unsigned tid = threadIdx.x;
    shared[tid + (padded ? tid / 32 : 0)] = value;
    __syncthreads();
    float initial = addition ? 0.0f : -FLT_MAX;
    float result = initial;
    unsigned warps = blockDim.x / 32;
    if (tid < 32 && tid < warps) {
        #pragma unroll
        for (unsigned i = 0; i < 32; ++i) {
            float next = shared[tid * (padded ? 33 : 32) + i];
            result = addition ? result + next : (result < next ? next : result);
        }
        __syncwarp((unsigned)((1ull << warps) - 1));
        shared[tid] = result;
    }
    __syncthreads();
    if (tid == 0) {
        result = initial;
        for (unsigned i = 0; i < warps; ++i) {
            float next = shared[i];
            result = addition ? result + next : (result < next ? next : result);
        }
        shared[0] = result;
    }
    __syncthreads();
    return shared[0];
}

template<bool padded>
__device__ __forceinline__ void softmax_body(float *output, const float *input, unsigned cols) {
    extern __shared__ float shared[];
    input += (unsigned long long)blockIdx.x * cols;
    output += (unsigned long long)blockIdx.x * cols;
    float maximum = -FLT_MAX;
    for (unsigned i = threadIdx.x; i < cols; i += blockDim.x)
        maximum = fmaxf(maximum, input[i]);
    maximum = ordered_reduce<padded, false>(maximum, shared);
    float sum = 0.0f;
    for (unsigned i = threadIdx.x; i < cols; i += blockDim.x)
        sum += expf(input[i] - maximum);
    sum = ordered_reduce<padded, true>(sum, shared);
    for (unsigned i = threadIdx.x; i < cols; i += blockDim.x)
        output[i] = expf(input[i] - maximum) / sum;
}

extern "C" __global__ void softmax_original_order(float *output, const float *input, unsigned cols) {
    softmax_body<false>(output, input, cols);
}

extern "C" __global__ void softmax_padded_order(float *output, const float *input, unsigned cols) {
    softmax_body<true>(output, input, cols);
}

extern "C" __global__ void softmax_padded_cached(float *output, const float *input, unsigned cols) {
    extern __shared__ float shared[];
    input += (unsigned long long)blockIdx.x * cols;
    output += (unsigned long long)blockIdx.x * cols;
    float values[3];
    float maximum = -FLT_MAX;
    #pragma unroll
    for (unsigned j = 0; j < 3; ++j) {
        unsigned i = threadIdx.x + j * blockDim.x;
        values[j] = i < cols ? input[i] : -FLT_MAX;
        if (i < cols) maximum = fmaxf(maximum, values[j]);
    }
    maximum = ordered_reduce<true, false>(maximum, shared);
    float sum = 0.0f;
    #pragma unroll
    for (unsigned j = 0; j < 3; ++j) {
        if (threadIdx.x + j * blockDim.x < cols) {
            values[j] = expf(values[j] - maximum);
            sum += values[j];
        }
    }
    sum = ordered_reduce<true, true>(sum, shared);
    #pragma unroll
    for (unsigned j = 0; j < 3; ++j) {
        unsigned i = threadIdx.x + j * blockDim.x;
        if (i < cols) output[i] = values[j] / sum;
    }
}

__device__ __forceinline__ float parallel_max(float value, float *shared) {
    for (unsigned offset = 16; offset; offset /= 2)
        value = fmaxf(value, __shfl_down_sync(0xffffffff, value, offset));
    if (threadIdx.x % 32 == 0) shared[threadIdx.x / 32] = value;
    __syncthreads();
    if (threadIdx.x < 32) {
        value = threadIdx.x < blockDim.x / 32 ? shared[threadIdx.x] : -FLT_MAX;
        for (unsigned offset = 16; offset; offset /= 2)
            value = fmaxf(value, __shfl_down_sync(0xffffffff, value, offset));
        if (threadIdx.x == 0) shared[0] = value;
    }
    __syncthreads();
    return shared[0];
}

extern "C" __global__ void softmax_parallel_max(float *output, const float *input, unsigned cols) {
    extern __shared__ float shared[];
    input += (unsigned long long)blockIdx.x * cols;
    output += (unsigned long long)blockIdx.x * cols;
    float values[3];
    float maximum = -FLT_MAX;
    #pragma unroll
    for (unsigned j = 0; j < 3; ++j) {
        unsigned i = threadIdx.x + j * blockDim.x;
        values[j] = i < cols ? input[i] : -FLT_MAX;
        if (i < cols) maximum = fmaxf(maximum, values[j]);
    }
    maximum = parallel_max(maximum, shared);
    float sum = 0.0f;
    #pragma unroll
    for (unsigned j = 0; j < 3; ++j) {
        if (threadIdx.x + j * blockDim.x < cols) {
            values[j] = expf(values[j] - maximum);
            sum += values[j];
        }
    }
    sum = ordered_reduce<true, true>(sum, shared);
    #pragma unroll
    for (unsigned j = 0; j < 3; ++j) {
        unsigned i = threadIdx.x + j * blockDim.x;
        if (i < cols) output[i] = values[j] / sum;
    }
}
