import os
import json
import logging
import hashlib
from tree_sitter import Language, Parser
from .llm import describe_code, rate_code
import json
from tinydb import TinyDB, Query
from tinydb.storages import MemoryStorage
import datetime

tinydb = None #this holds the tree in memory and makes it a lil more queryable

def _build_language_library(full_path):
    languages = {
        'python': f'{full_path}/vendor/tree-sitter-python',
        'javascript': f'{full_path}/vendor/tree-sitter-javascript',
        'java': f'{full_path}/vendor/tree-sitter-java',
        'ruby': f'{full_path}/vendor/tree-sitter-ruby',
        # Add more languages as needed
    }

    for lang, path in languages.items():
        logging.info("Building language library for %s from %s", lang, path)

    Language.build_library(
        'build/my-languages.so',
        list(languages.values())
    )
    return {lang: Language('build/my-languages.so', lang) for lang in languages}

def _get_language_from_extension(file_extension, languages):
    language_mapping = {
        '.py': 'python',
        '.js': 'javascript',
        '.java': 'java',
        '.rb': 'ruby',
        # Map other extensions to languages
    }
    language_name = language_mapping.get(file_extension)
    return languages.get(language_name)

def _parse_file(file_path, language):
    with open(file_path, 'r', encoding='utf-8') as f:
        source_code = f.read()
    parser = Parser()
    parser.set_language(language)
    tree = parser.parse(bytes(source_code, 'utf8'))

    return tree, source_code

def _extract_function_calls(node, source_code, language):
    function_calls = []

    # Define call expression node types for different languages
    if language == 'python':
        call_node_types = ['call_expression']
    # Add more language-specific logic here for other languages

    else:
        call_node_types = ['call_expression']  # Default case (fallback)

    stack = [node]
    while stack:
        current_node = stack.pop()

        # Check if the current node matches any of the call expression types
        if current_node.type in call_node_types:
            # Extract the function name directly from the source_code string
            function_name = source_code[current_node.children[0].start_byte:current_node.children[0].end_byte]
            function_calls.append(function_name)

        for child in current_node.children:
            stack.append(child)

    return function_calls

def _extract_comments_and_docstrings(node, source_code):
    comments = []
    docstring = None

    stack = [node]
    while stack:
        current_node = stack.pop()

        if current_node.type == 'comment':
            comment_text = source_code[current_node.start_byte:current_node.end_byte].strip()
            comments.append(comment_text)
        elif current_node.type == 'string' and not docstring:
            # Assuming the first string in a function is the docstring
            docstring = source_code[current_node.start_byte:current_node.end_byte].strip()

        for child in current_node.children:
            stack.append(child)

    return comments, docstring

def _extract_imports(node, source_code):
    imports = []

    stack = [node]
    while stack:
        current_node = stack.pop()

        if current_node.type == 'import_statement':
            import_text = source_code[current_node.start_byte:current_node.end_byte].strip()
            imports.append(import_text)

        for child in current_node.children:
            stack.append(child)

    return imports

def _calculate_cyclomatic_complexity(node):
    complexity = 1
    stack = [node]

    while stack:
        current_node = stack.pop()

        # Increase complexity for each control flow structure
        if current_node.type in ('if_statement', 'for_statement', 'while_statement', 'switch_statement', 'try_statement', 'case_statement'):
            complexity += 1

        for child in current_node.children:
            stack.append(child)

    return complexity

def _calculate_nesting_depth(node):
    max_depth = 0
    stack = [(node, 0)]

    while stack:
        current_node, current_depth = stack.pop()

        # Track max depth for control flow structures
        if current_node.type in ('if_statement', 'for_statement', 'while_statement', 'switch_statement'):
            max_depth = max(max_depth, current_depth + 1)

        for child in current_node.children:
            stack.append((child, current_depth + 1))

    return max_depth

def _count_lines_of_code(source_code):
    return len(source_code.splitlines())

def _extract_top_level_statements(node, source_code):
    statements = []
    imports = []
    stack = [node]
    while stack:
        current_node = stack.pop()

        # Capture top-level imports
        if current_node.type == 'import_statement':
            import_text = source_code[current_node.start_byte:current_node.end_byte].strip()
            imports.append(import_text)
        elif current_node.type == 'import_from_statement':
            import_text = source_code[current_node.start_byte:current_node.end_byte].strip()
            imports.append(import_text)

        for child in current_node.children:
            stack.append(child)
    data = {}
    data['imports'] = imports
    data['code'] = _extract_top_level_code(node, source_code, imports)
    statements.append(data)
    return statements

def _get_code_location(node):
    """
    Extracts the line and character positions from a Tree-sitter node.
    """
    start_position = {
        "line": node.start_point[0] + 1,  # Line numbers start at 0 in Tree-sitter, so we add 1
        "character": node.start_point[1]   # Character position starts at 0
    }
    end_position = {
        "line": node.end_point[0] + 1,
        "character": node.end_point[1]
    }
    return {
        "start": start_position,
        "end": end_position
    }

def _extract_function_calls(node, source_code):
    function_calls = []

    stack = [node]
    while stack:
        current_node = stack.pop()

        # Check if the current node is a function call
        if current_node.type == 'call':
            # The first child of a call node is often an identifier or an attribute (for method calls)
            if current_node.children:
                function_name_node = current_node.children[0]
                function_name = source_code[function_name_node.start_byte:function_name_node.end_byte]
                function_calls.append(function_name)

        # Continue traversing the tree
        for child in current_node.children:
            stack.append(child)

    return function_calls


#    cc = code complexity
#    loc = lines of code
#    ctd = control flow depth
#    nfc = number of function calls
#    nv = number of variables
#    cca = LLM code readability/understandability metric 
def _composite_complexity_metric(cc, loc, ctd, nfc, nv, cca, 
                                max_cc, max_loc, max_ctd, max_nfc, max_nv):
    # Normalize each metric
    normalized_cc = cc / max_cc if max_cc > 0 else 0
    normalized_loc = loc / max_loc if max_loc > 0 else 0
    normalized_ctd = ctd / max_ctd if max_ctd > 0 else 0
    normalized_nfc = nfc / max_nfc if max_nfc > 0 else 0
    normalized_nv = nv / max_nv if max_nv > 0 else 0
    normalized_cca = cca  # Already between 0 and 1
                            # 0 is good, 1 is bad

    # Weighted sum of the normalized values
    return (0.2 * normalized_cc +  
            0.15 * normalized_loc + 
            0.15 * normalized_ctd + 
            0.15 * normalized_nfc + 
            0.15 * normalized_nv + 
            0.2 * normalized_cca)

def _extract_definitions_and_calls(node, source_code, filename, ai_model):
    definitions = []

    stack = [node]
    while stack:
        current_node = stack.pop()

        if current_node.type in ('function_definition', 'function_declaration', 'method_definition'):
            # Extract the function name directly from the source_code string
            func_name = source_code[current_node.children[1].start_byte:current_node.children[1].end_byte]
            func_code = source_code[current_node.start_byte:current_node.end_byte]  # Capture full function code
            
            # Initialize lists to store different elements
            called_functions = []
            imports = []
            control_flow = []
            variables = []
            node_types = []

            # Traverse the function body to capture additional details
            function_stack = [current_node]
            while function_stack:
                function_node = function_stack.pop()

                node_types.append(function_node.type)

                # Identify control flow structures
                if function_node.type in ('if_statement', 'for_statement', 'while_statement', 'switch_statement'):
                    control_flow.append(function_node.type)

                # Identify variable assignments
                if function_node.type in ('assignment', 'variable_declaration', 'parameter', 'identifier'):
                    variable_name = source_code[function_node.start_byte:function_node.end_byte].strip()
                    variables.append(variable_name)

                # Identify function calls
                if function_node.type == 'call_expression':
                    function_name = source_code[function_node.children[0].start_byte:function_node.children[0].end_byte]
                    called_functions.append(function_name)


                # Capture imports
                if function_node.type == 'import_statement':
                    import_text = source_code[function_node.start_byte:function_node.end_byte].strip()
                    imports.append(import_text)

                # Continue traversing the function body
                for child in function_node.children:
                    function_stack.append(child)

            # Calculate complexity metrics
            lines_of_code = _count_lines_of_code(func_code)
            cyclomatic_complexity = _calculate_cyclomatic_complexity(current_node)
            nesting_depth = _calculate_nesting_depth(current_node)
            number_of_variables = len(variables)
            called_functions = _extract_function_calls(current_node, source_code)
            number_of_function_calls = len(called_functions)
            description = _llm_code("description", func_name, func_code, filename, ai_model)
            llm_code_score = _llm_code("score", func_name, func_code, filename, ai_model)
            try:
                llm_code_score = float(llm_code_score)
            except Exception as e:
                logging.error("Error in LLM code score for %s, %s", func_name, e)
                llm_code_score = 0.5

            # Store the extracted details
            definitions.append({
                'type': 'function',
                'name': func_name,
                'code': func_code,  # Include the full function code
                'lines_of_code': lines_of_code,
                'cyclomatic_complexity': cyclomatic_complexity,
                'llm_code_readablity': llm_code_score,
                'nesting_depth': nesting_depth,
                'number_of_variables': number_of_variables,
                'number_of_function_calls': number_of_function_calls,
                'calls': called_functions,
                'description': description,                
                'location': _get_code_location(current_node),  # Add this line to include location
                'imports': imports,
            })

        elif current_node.type == 'class_definition':
            class_name = source_code[current_node.children[1].start_byte:current_node.children[1].end_byte]
            class_code = source_code[current_node.start_byte:current_node.end_byte]  # Capture full class code

            definitions.append({
                'type': 'class',
                'name': class_name,
                'code': class_code,  # Include the full class code
                'methods': []
            })

        for child in current_node.children:
            stack.append(child)

    return definitions

def _llm_code(which, func_name, func_code, filename, ai_model):
    hashedcode = ""
    if which == "description":
        hashedcode = hashlib.md5(func_code.encode()).hexdigest()
    elif which == "score":
        score_code = "score\t" + func_code
        hashedcode = hashlib.md5(score_code.encode()).hexdigest()
    # check if we've already generated a description for this:
    desc_filename = f"./output/cache/{hashedcode}.txt"
    if os.path.exists(desc_filename):
        with open(desc_filename, "r", encoding="utf-8") as f:
            return f.read()
    # if not, generate a description
    ai = ai_model.split("|")[0]
    model = ai_model.split("|")[1]
    if which == "description":
        content = describe_code(func_name, func_code, filename, ai, model)
    elif which == "score":
        content = rate_code(func_name, func_code, filename, ai, model)
    f = open(desc_filename, "w", encoding="utf-8")
    f.write(content)
    f.close()
    return content 



def _map_repository(repo_path, languages, ai_model):
    repo_map = {}
    for root, _, files in os.walk(repo_path):
        for file in files:
            file_extension = os.path.splitext(file)[1]
            language = _get_language_from_extension(file_extension, languages)
            if language:
                file_path = os.path.join(root, file)
                repo_map[file_path] = {}
                repo_map[file_path]["file_extension"] = file_extension

                tree, source_code = _parse_file(file_path, language)

                # Extract top-level statements
                top_level_statements = _extract_top_level_statements(tree.root_node, source_code)

                repo_map[file_path]['top-level'] = top_level_statements

                definitions = _extract_definitions_and_calls(tree.root_node, source_code, file_path, ai_model)
                repo_map[file_path]['functions'] = definitions

    max_vals = _get_max_vals(repo_map)
    repo_map = _add_composite_complexity(repo_map, max_vals)    

    return repo_map

def _add_composite_complexity(repo_map, max_vals):
    max_cc = max_vals[0]
    max_loc = max_vals[1]
    max_ctd = max_vals[2]
    max_nfc = max_vals[3]
    max_nv = max_vals[4]

    for f in repo_map:
        file = repo_map[f]
        funcs = file['functions']
        for func in funcs:
            if func['type'] == 'function':
                cc = func['cyclomatic_complexity']
                loc = func['lines_of_code']
                ctd = func['nesting_depth']
                nfc = func['number_of_function_calls']
                nv = func['number_of_variables']
                cca = func['llm_code_readablity'] #LLM code readability/understandability metric
                composite = _composite_complexity_metric(cc, loc, ctd, nfc, nv, cca, max_cc, max_loc, max_ctd, max_nfc, max_nv)
                func['composite_complexity'] = composite
    return repo_map

def _get_max_vals(repo_map):
    max_cc = 0
    max_loc = 0
    max_ctd = 0
    max_nfc = 0
    max_nv = 0
    for f in repo_map:
        file = repo_map[f]
        functions = file['functions']
        for func in functions:
            if func['type'] == 'function':
                cc = func['cyclomatic_complexity']
                if cc > max_cc:
                    max_cc = cc
                loc = func['lines_of_code']
                if loc > max_loc:
                    max_loc = loc
                ctd = func['nesting_depth']
                if ctd > max_ctd:
                    max_ctd = ctd
                nfc = func['number_of_function_calls']
                if nfc > max_nfc:
                    max_nfc = nfc
                nv = func['number_of_variables']
                if nv > max_nv:
                    max_nv = nv
    return [max_cc, max_loc, max_ctd, max_nfc, max_nv]

def _extract_top_level_code(root_node, source_code, imports):
    top_level_code = []
    stack = [root_node]

    while stack:
        current_node = stack.pop()

        # Skip function and method nodes (and their children)
        if current_node.type in ["function_definition", "method_definition"]:
            continue

        # Skip fragmentary nodes
        if current_node.type in ["identifier", "argument_list", "parameters", "call_expression", "pair", "object", "array", "property_identifier"]:
            continue

        # Check if the node is a direct child of the root (top-level code)
        if not _is_within_function(current_node) and _is_whole_statement(current_node):
            start_point = current_node.start_point
            end_point = current_node.end_point
            
            # Use start and end points to extract the code directly
            start_char = _point_to_index(source_code, start_point)
            end_char = _point_to_index(source_code, end_point)
            
            # Append the extracted code to the list as a whole string
            code_segment = source_code[start_char:end_char].strip()
            if code_segment and code_segment not in imports and code_segment not in top_level_code:
                top_level_code.append(code_segment)

        # Continue traversal only if the node isn't part of a larger expression
        if current_node.type not in ["expression_statement", "import_statement", "block", "if_statement", "for_statement", "while_statement"]:
            stack.extend(current_node.children)

    return top_level_code

def _is_within_function(node):
    """Utility function to check if a node is within a function or method definition."""
    while node.parent:
        if node.parent.type in ["function_definition", "method_definition"]:
            return True
        node = node.parent
    return False

def _is_whole_statement(node):
    """Check if the node represents a whole statement rather than a fragment."""
    return node.type in ["expression_statement", "import_statement", "if_statement", "for_statement", "while_statement", "block", "return_statement", "variable_declaration"]

def _point_to_index(source_code, point):
    """Convert a Tree-sitter Point (row, column) to a character index in the source code."""
    lines = source_code.splitlines(True)
    row, column = point
    # Calculate the character index from the row and column
    return sum(len(line) for line in lines[:row]) + column


def build_tree(full_path, repo_parent, repo_name, ai_model):
    # list current directory
    logging.info("Build_Tree using current working dir: %s", os.getcwd())

    languages = _build_language_library(full_path)

    repo_path = f'./output/{repo_parent}-{repo_name}/_source'
    repo_map = _map_repository(repo_path, languages, ai_model)

    filename = f'./output/{repo_parent}-{repo_name}_repo_map.json'

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(repo_map, f, indent=4)


def init_tinydb(repo_parent, repo_name):
    filename = f'./output/{repo_parent}-{repo_name}_repo_map.json'
    tinyname = f'./output/{repo_parent}-{repo_name}_tinydb.json'
    # Load the JSON data from the file
    with open(filename, 'r', encoding='utf-8') as file:
        data = json.load(file)

    # get rid of existing tiny name if it exists
    if os.path.exists(tinyname):
        os.remove(tinyname)

    # Initialize TinyDB 
    db = TinyDB(tinyname) #storing it so the webserver can use it later

    # Insert the data into TinyDB
    for file_path, details in data.items():
        sum_complexity = 0
        count_functions = 0
        functions = []
        if 'functions' in details:
            for function in details['functions']:
                # Track the maximum composite complexity for this file
                complexity = function.get('composite_complexity', 0)
                if complexity > 0:
                    sum_complexity += complexity
                    count_functions += 1
                dx = {
                    'file_path': file_path,
                    'function_name': function.get('name'),
                    'composite_complexity': complexity,
                    'lines_of_code': function.get('lines_of_code'),
                    'cyclomatic_complexity': function.get('cyclomatic_complexity'),
                    'llm_code_readability': function.get('llm_code_readablity'),
                    'nesting_depth': function.get('nesting_depth'),
                    'number_of_variables': function.get('number_of_variables'),
                    'number_of_function_calls': function.get('number_of_function_calls'),
                    'description': function.get('description'),
                    'source': function.get('code'),
                    'location': function.get('location'),
                }
                functions.append(dx)

        # Insert the file with its max complexity

        db.insert({
            'file_path': file_path,
            'avg_composite_complexity': sum_complexity / count_functions if count_functions > 0 else 0,
            'functions': functions
        })   

    # Get the last modification time as a timestamp
    timestamp = os.path.getmtime(filename)
    timestamp = datetime.datetime.fromtimestamp(timestamp).isoformat()
    db.insert({'last_modified': timestamp})
    

    global tinydb # assign this to the global value so we can have access from other spots
    tinydb = db
