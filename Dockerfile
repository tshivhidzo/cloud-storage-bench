# Reproduction container: the byte-reproducibility boundary for the bootstrap
# draw file. Base pinned to the linux/amd64 IMAGE digest of python:3.10.12-slim
# (platform-specific, not the multi-arch manifest list, so the byte-identity
# guarantee is tied to one concrete image).
FROM --platform=linux/amd64 python@sha256:13cc673c11ee90d6ba92d95f35f4d8e59148937f1e3b4044788e93268bfe9d2e
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1
WORKDIR /work
COPY requirements-lock.txt .
RUN pip install --no-cache-dir -r requirements-lock.txt
COPY . .
# Default: regenerate the ENTIRE chain INCLUDING all five bootstrap batches
# from scratch, then verify the regenerated draw file's SHA-256 against the
# committed one, then run the regression tests.
CMD ["bash", "sweep/container_verify.sh"]
