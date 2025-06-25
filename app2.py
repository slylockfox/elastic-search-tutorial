import re
from flask import Flask, render_template, request
from search2 import Search2

app = Flask(__name__)
es = Search2()

# @app.route("/")
# def hello_world():
#     return "<p>Hello, World!</p>"

@app.get('/')
def index():
    return render_template('index.html')

@app.post('/')
def handle_search():
    query = request.form.get('query', '')
    filters, parsed_query = extract_filters(query)
    from_ = request.form.get('from_', type=int, default=0)

    results = es.search_template(
        body={
            'params': {
                'unquoted_search_terms': parsed_query,
                **filters
            }
        }
    )

    aggs = []

    if results['hits']['total']['value'] < 0:
        search_query = {
            'sparse_vector': {
                "field": "title_elser_embedding",
                "inference_id": ".elser_model_2_linux-x86_64",
                "query":  es.get_embedding(parsed_query)
                }
            }   
        results = es.search(
            query={
                **search_query
            },
            size=5,
            from_=from_
        )

    else: # add aggs if not vector search
        aggs = {
            'Categories': {
                bucket['key']: bucket['doc_count']
                for bucket in results['aggregations']['categories']['buckets']
            }
        }
    
    return render_template('index2.html', results=results['hits']['hits'],
                            query=query, from_=from_,
                            total=results['hits']['total']['value'],
                            aggs=aggs)

@app.get('/document/<id>')
def get_document(id):
    document = es.retrieve_document(id)
    title = document['_source']['name']
    paragraphs = document['_source']['content'].split('\n')
    return render_template('document.html', title=title, paragraphs=paragraphs)

@app.cli.command()
def reindex():
    """Regenerate the Elasticsearch index."""
    response = es.reindex()
    print(f'Index with {len(response["items"])} documents created '
            f'in {response["took"]} milliseconds.')
    
def extract_filters(query):
    filters = []

    filter_regex = r'categories:([^\s]+)\s*'
    m = re.search(filter_regex, query)
    if m:
        filters.append({
            'term': {
                'categories': {
                    'value': m.group(1)
                }
            },
        })
        query = re.sub(filter_regex, '', query).strip()

    filter_regex = r'year:([^\s]+)\s*'
    m = re.search(filter_regex, query)
    if m:
        filters.append({
            'range': {
                'updated_at': {
                    'gte': f'{m.group(1)}||/y',
                    'lte': f'{m.group(1)}||/y',
                }
            },
        })
        query = re.sub(filter_regex, '', query).strip()

    return {'filters': filters}, query
