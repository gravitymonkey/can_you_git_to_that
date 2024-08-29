import os
import logging
import traceback
from llama_index.core import SimpleDirectoryReader, Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core import Settings
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core import SummaryIndex, VectorStoreIndex
from llama_index.core.tools import QueryEngineTool
from llama_index.core.query_engine.router_query_engine import RouterQueryEngine
from llama_index.core.selectors import LLMSingleSelector
from llama_index.core import StorageContext, load_index_from_storage
import pathspec
import shutil
from .code_tree import get_tinydb

logging.basicConfig(level=logging.INFO)

query_engine = None

#class CustomOpenAI(OpenAI):
#    def _prepare_chat_with_tools(self, *args, **kwargs):
        # Implement the abstract method here.
#        pass

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

def _build_rag(force_rebuild_rag, repo_full_path, repo_parent, repo_name):
    try:
        logging.info("force rebuild rag: %s; repo_full_path: %s", force_rebuild_rag, repo_full_path)
        dir_name = f"./output/{repo_parent}-{repo_name}_rag"
        summary_index = None
        vector_index = None

        openai_key = os.environ.get("OPENAI_API_KEY")
        Settings.llm = OpenAI(api_key=openai_key, model="gpt-4o-mini")
        Settings.embed_model = OpenAIEmbedding(api_key=openai_key, model="text-embedding-3-large")

        if force_rebuild_rag or not _rag_exists(dir_name, ["summary", "vector", "code_vector"]):
            logging.info("Building/rebuilding RAG")

            documents = SimpleDirectoryReader(f"./output/{repo_parent}-{repo_name}/_source").load_data()
            # read the copy of the source, so we won't read/index anything in .gitignore
            splitter = SentenceSplitter(chunk_size=1024)
            nodes = splitter.get_nodes_from_documents(documents)

            summary_index = SummaryIndex(nodes)
            summary_index.storage_context.persist(persist_dir=os.path.join(dir_name, 'summary'))

            documents = _get_function_descriptions()
            logging.info("Function descriptions got %s docs", len(documents))
            nodes = splitter.get_nodes_from_documents(documents)
            vector_index = VectorStoreIndex(nodes)
            vector_index.storage_context.persist(persist_dir=os.path.join(dir_name, 'vector'))

            documents = _get_function_sourcecode()
            logging.info("Function source got %s docs", len(documents))
            nodes = splitter.get_nodes_from_documents(documents)
            code_vector_index = VectorStoreIndex(nodes)
            code_vector_index.storage_context.persist(persist_dir=os.path.join(dir_name, 'code_vector'))

        else:
            # reload RAG
            logging.info("Loading RAG from storage")
            summary_storage_context = StorageContext.from_defaults(persist_dir=os.path.join(dir_name, 'summary'))
            vector_storage_context = StorageContext.from_defaults(persist_dir=os.path.join(dir_name, 'vector'))
            code_vector_storage_context = StorageContext.from_defaults(persist_dir=os.path.join(dir_name, 'code_vector'))   
            summary_index = load_index_from_storage(summary_storage_context)
            vector_index = load_index_from_storage(vector_storage_context)
            code_vector_index = load_index_from_storage(code_vector_storage_context)

# may not need the rest of this method, if we don't use RAG within the main app.
# we just build indices and save them to disk, and then load them later

        summary_query_engine = summary_index.as_query_engine(
            response_mode="tree_summarize",
        )
        vector_query_engine = vector_index.as_query_engine()
        code_query_engine = code_vector_index.as_query_engine()

        summary_tool = QueryEngineTool.from_defaults(
            query_engine=summary_query_engine,
            description=(
                "Useful for summarization questions related to the codebase."
            ),
        )

        vector_tool = QueryEngineTool.from_defaults(
            query_engine=vector_query_engine,
            description=(
                "Useful for asking plain-language questions from descriptions of the codebase."
            ),  
        )

        code_vector_tool = QueryEngineTool.from_defaults(
            query_engine=code_query_engine,
            description=(
                "Useful for questions about the source code itself."
            ),
        )


        query_engine = RouterQueryEngine(
            selector=LLMSingleSelector.from_defaults(),
            query_engine_tools=[
                summary_tool,
                vector_tool,
                code_vector_tool,
            ],
            verbose=True
        )
        return query_engine

    except Exception as e:
        logging.error("Error building RAG: %s", e)
        traceback.print_exc()
        raise e
    
def _get_function_descriptions():
    docs = []
    try:
        db = get_tinydb()
        for d in db.all():
            filename = d.get('file_path', None)
            if filename:
                functions = d.get('functions', None)
                if functions:
                    for f in functions:
                        function_name = f.get('function_name', None)
                        description = f.get('description', None)
                        if function_name and description:
                            logging.debug("Adding function description %s from %s to RAG", function_name, filename)
                            document = Document(
                                text=description,
                                metadata={"filename": filename, "function_name": function_name},
                            )
                            docs.append(document)
        return docs
    except Exception as e:
        logging.error("Error getting function definitions: %s", e)
        traceback.print_exc()
        raise e
    
def _get_function_sourcecode():
    docs = []
    try:
        db = get_tinydb()
        for d in db.all():
            filename = d.get('file_path', None)
            if filename:
                functions = d.get('functions', None)
                if functions:
                    for f in functions:
                        function_name = f.get('function_name', None)
                        source = f.get('source', None)
                        if function_name and source:
                            logging.info("Adding function source %s from %s to RAG", function_name, filename)
                            location = f.get('location', '')
                            document = Document(
                                text=source,
                                metadata={"filename": filename, 
                                          "function_name": function_name,
                                          "location": location
                                          },
                            )
                            docs.append(document)
        return docs
    except Exception as e:
        logging.error("Error getting function definitions: %s", e)
        traceback.print_exc()
        raise e



def copy_code(full_path, repo_parent, repo_name):
    try:
        dir_name = f"./output/{repo_parent}-{repo_name}/_source"
        logging.info("Copy relevant code from %s to %s", full_path, dir_name)

        # Empty the directory first
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
        os.makedirs(dir_name, exist_ok=True)

        # Read the .gitignore file
        gitignore_path = os.path.join(full_path, '.gitignore')
        if os.path.exists(gitignore_path):
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                gitignore_patterns = f.read().splitlines()
        else:
            gitignore_patterns = []
        gitignore_patterns.append('.git')

        # Compile the gitignore patterns
        spec = pathspec.PathSpec.from_lines('gitwildmatch', gitignore_patterns)

        for root, dirs, files in os.walk(full_path):
            for file in files:
                file_path = os.path.relpath(os.path.join(root, file), full_path)
                # Check if the file matches any of the gitignore patterns
                if not spec.match_file(file_path):
                    # Determine the destination path
                    dest_path = os.path.join(dir_name, file_path)
                    # Create the destination directory if it doesn't exist
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    # Copy the file
                    shutil.copy2(os.path.join(root, file), dest_path)
                    logging.info("Copied %s to %s", file_path, dest_path)

    except Exception as e:
        logging.error("Error copying code: %s", e)
        traceback.print_exc()
        raise e


def init_rag(force_rebuild, full_path, repo_owner, repo_name):
    global query_engine
    query_engine = _build_rag(force_rebuild, full_path, repo_owner, repo_name)  # Force rebuild for testing

def get_rag():
    return query_engine