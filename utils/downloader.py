from modelscope.hub.snapshot_download import snapshot_download
# llm_model_dir = snapshot_download('Qwen/Qwen2.5-0.5B-Instruct',cache_dir='models')
emb_model_dir = snapshot_download('AI-ModelScope/bge-large-zh-v1.5',cache_dir='models')