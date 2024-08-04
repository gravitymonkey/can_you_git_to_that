import os
import logging
import traceback
from llama_index.core import SimpleDirectoryReader
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core import Settings
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core import SummaryIndex, VectorStoreIndex
from llama_index.core.tools import QueryEngineTool
from llama_index.core.query_engine.router_query_engine import RouterQueryEngine
from llama_index.core.selectors import LLMSingleSelector
from llama_index.core import StorageContext, load_index_from_storage

logging.basicConfig(level=logging.INFO)

query_engine = None

class CustomOpenAI(OpenAI):
    def _prepare_chat_with_tools(self, *args, **kwargs):
        # Implement the abstract method here.
        pass

def _rag_exists(dir_name, subdirs):
    index_exists = False
    # Create the output directory if it doesn't exist
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)    
        for subdir in subdirs:
            os.makedirs(os.path.join(dir_name, subdir))
    else:
        index_exists = True

    return index_exists

def _build_rag(force_rebuild_rag, repo_full_path, repo_name):
    try:
        logging.info("force rebuild rag: %s; repo_full_path: %s", force_rebuild_rag, repo_full_path)
        dir_name = f"../output/{repo_name}_rag"
        summary_index = None
        vector_index = None

        openai_key = os.environ.get("OPENAI_API_KEY")
        Settings.llm = CustomOpenAI(api_key=openai_key, model="gpt-4o-mini")
        Settings.embed_model = OpenAIEmbedding(api_key=openai_key, model="text-embedding-3-large")

        if force_rebuild_rag or not _rag_exists(dir_name, ["summary", "vector"]):
            logging.info("Building/rebuilding RAG")
            documents = SimpleDirectoryReader(repo_full_path).load_data()
            splitter = SentenceSplitter(chunk_size=1024)
            nodes = splitter.get_nodes_from_documents(documents)
            summary_index = SummaryIndex(nodes)
            summary_index.storage_context.persist(persist_dir=os.path.join(dir_name, 'summary'))
            vector_index = VectorStoreIndex(nodes)
            vector_index.storage_context.persist(persist_dir=os.path.join(dir_name, 'vector'))
        else:
            # Rebuild storage context
            logging.info("Loading RAG from storage")
            summary_storage_context = StorageContext.from_defaults(persist_dir=os.path.join(dir_name, 'summary'))
            vector_storage_context = StorageContext.from_defaults(persist_dir=os.path.join(dir_name, 'vector'))
            summary_index = load_index_from_storage(summary_storage_context)
            vector_index = load_index_from_storage(vector_storage_context)

        summary_query_engine = summary_index.as_query_engine(
            response_mode="tree_summarize",
        )
        vector_query_engine = vector_index.as_query_engine()

        summary_tool = QueryEngineTool.from_defaults(
            query_engine=summary_query_engine,
            description=(
                "Useful for summarization questions related to the codebase."
            ),
        )

        vector_tool = QueryEngineTool.from_defaults(
            query_engine=vector_query_engine,
            description=(
                "Useful for retrieving specific context from the codebase."
            ),  
        )

        query_engine = RouterQueryEngine(
            selector=LLMSingleSelector.from_defaults(),
            query_engine_tools=[
                summary_tool,
                vector_tool,
            ],
            verbose=True
        )
        return query_engine

    except Exception as e:
        logging.error("Error building RAG: %s", e)
        traceback.print_exc()
        raise e

def init_rag(force_rebuild, full_path, repo_name):
    global query_engine
    query_engine = _build_rag(force_rebuild, full_path, repo_name)  # Force rebuild for testing

def get_rag():
    return query_engine