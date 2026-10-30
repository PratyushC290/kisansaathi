# Hugging Face Spaces (Docker SDK) / Render / any container host.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    HOME=/home/user HF_HOME=/home/user/.cache/huggingface PORT=7860
RUN useradd -m -u 1000 user
WORKDIR /home/user/app

# CPU-only torch keeps the image ~2 GB smaller than the default CUDA build.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=user . .
USER user
# Build the knowledge base into the image: downloads the official PDFs + embedding model once.
RUN python -m kisansaathi.rag.ingest

EXPOSE 7860
CMD streamlit run app/ui.py --server.port ${PORT} --server.address 0.0.0.0 --server.headless true
