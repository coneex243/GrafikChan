import os
import re
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
import PyPDF2
from io import BytesIO
import networkx as nx
import uuid

# Telegram bot token
from dotenv import load_dotenv

load_dotenv()

# Telegram bot token loaded from environment variables or .env file
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Function to parse text input for structured data
def parse_text(text):
    data = []
    current_entry = {}
    lines = text.split('\n')
    current_collection = None

    for line in lines:
        line = line.strip()
        if line.startswith('_collection:'):
            if current_entry and any(current_entry.get(k) for k in ['phone', 'fio', 'email', 'address']):
                data.append(current_entry)
                current_entry = {}
            current_collection = line.split(':')[1].strip()
            current_entry['collection'] = current_collection
        elif ':' in line or '=' in line:
            delimiter = ':' if ':' in line else '='
            key, value = map(str.strip, line.split(delimiter, 1))
            key = key.lower().replace(' ', '_')
            if key not in current_entry or (key in ['phone', 'fio', 'email', 'address'] and current_entry[key] != value):
                current_entry[key] = value
        elif line and current_collection:  # Handle lines like "MOONAPI" or "PROXYNOVA"
            current_entry['source'] = line

    if current_entry and any(current_entry.get(k) for k in ['phone', 'fio', 'email', 'address']):
        data.append(current_entry)
    
    # Deduplicate entries based on phone or fio
    unique_data = []
    seen = set()
    for entry in data:
        key = (entry.get('phone'), entry.get('fio'))
        if key not in seen:
            seen.add(key)
            unique_data.append(entry)
    return unique_data

# Function to parse PDF file
def parse_pdf(file_stream):
    text = ""
    pdf_reader = PyPDF2.PdfReader(file_stream)
    for page in pdf_reader.pages:
        text += page.extract_text() or ""
    return parse_text(text)

# Function to parse TXT file
def parse_txt(file_stream):
    text = file_stream.read().decode('utf-8')
    return parse_text(text)

# Function to create a network graph
def create_graph(data):
    G = nx.Graph()
    main_node = str(uuid.uuid4())  # Unique ID for the person
    G.add_node(main_node, label="Person", type="person", color="#FFA500", size=30)

    # Track unique values to avoid duplicate nodes
    seen_values = set()
    seen_nodes = {main_node}

    for entry in data:
        collection = entry.get('collection', 'unknown')
        # Handle names (fio, name, firstname, lastname, etc.)
        for key in ['fio', 'name', 'fullname']:
            if key in entry and entry[key] not in seen_values:
                node_id = str(uuid.uuid4())
                G.add_node(node_id, label=entry[key], type="name", color="#FFA500", size=20, collection=collection)
                G.add_edge(main_node, node_id, color="#00FFFF", label=collection)
                seen_values.add(entry[key])
                seen_nodes.add(node_id)

        # Handle phones
        for key in ['phone', 'phone2', 'phonemobile']:
            if key in entry and entry[key] not in seen_values:
                node_id = str(uuid.uuid4())
                G.add_node(node_id, label=entry[key], type="phone", color="#0000FF", size=15, collection=collection)
                G.add_edge(main_node, node_id, color="#00FFFF", label=collection)
                seen_values.add(entry[key])
                seen_nodes.add(node_id)

        # Handle emails
        for key in ['email', 'email2']:
            if key in entry and entry[key] not in seen_values:
                node_id = str(uuid.uuid4())
                G.add_node(node_id, label=entry[key], type="email", color="#800080", size=15, collection=collection)
                G.add_edge(main_node, node_id, color="#00FFFF", label=collection)
                seen_values.add(entry[key])
                seen_nodes.add(node_id)

        # Handle addresses
        for key in ['address', 'reg_address', 'addressconstantregistration', 'addresshome', 'placelife']:
            if key in entry and entry[key] not in seen_values:
                node_id = str(uuid.uuid4())
                G.add_node(node_id, label=entry[key], type="address", color="#008000", size=15, collection=collection)
                G.add_edge(main_node, node_id, color="#00FFFF", label=collection)
                seen_values.add(entry[key])
                seen_nodes.add(node_id)

        # Handle IDs (passport, snils, inn)
        for key in ['passport', 'snils', 'inn', 'passport_info']:
            if key in entry and entry[key] not in seen_values:
                node_id = str(uuid.uuid4())
                G.add_node(node_id, label=entry[key], type=key, color="#FF4500", size=15, collection=collection)
                G.add_edge(main_node, node_id, color="#00FFFF", label=collection)
                seen_values.add(entry[key])
                seen_nodes.add(node_id)

        # Handle breach data or other fields
        for key, value in entry.items():
            if key not in ['collection', 'fio', 'name', 'fullname', 'phone', 'phone2', 'phonemobile', 'email', 'email2', 'address', 'reg_address', 'addressconstantregistration', 'addresshome', 'placelife', 'passport', 'snils', 'inn', 'passport_info'] and value not in seen_values:
                node_id = str(uuid.uuid4())
                G.add_node(node_id, label=f"{key}: {value}", type="misc", color="#FFFFFF", size=10, collection=collection)
                G.add_edge(main_node, node_id, color="#00FFFF", label=collection)
                seen_values.add(value)
                seen_nodes.add(node_id)

    # Apply clustering for dense graphs
    if len(seen_nodes) > 20:
        clusters = nx.algorithms.community.greedy_modularity_communities(G)
        for i, cluster in enumerate(clusters):
            for node in cluster:
                if node in G.nodes:
                    G.nodes[node]['group'] = i

    return G

# Function to generate HTML report with vis.js
def generate_html_report(graph, data):
    nodes = []
    edges = []
    node_groups = {}
    for node, attr in graph.nodes(data=True):
        nodes.append({
            "id": node,
            "label": attr.get("label", node),
            "color": attr.get("color", "#FFFFFF"),
            "shape": "dot" if attr.get("type") == "person" else "box",
            "size": attr.get("size", 10),
            "title": f"Type: {attr.get('type', 'unknown')}<br>Collection: {attr.get('collection', 'N/A')}",
            "group": attr.get("group")
        })
        if attr.get("group") is not None:
            node_groups[node] = attr.get("group")

    for source, target, attr in graph.edges(data=True):
        edges.append({
            "from": source,
            "to": target,
            "color": {"color": attr.get("color", "#00FFFF")},
            "title": attr.get("label", "N/A"),
            "smooth": {"type": "curvedCW", "roundness": 0.2}
        })

    # Generate data summary
    summary = "<h2>Data Summary</h2><ul>"
    seen_entries = set()
    for entry in data:
        key = (entry.get('phone', ''), entry.get('fio', ''))
        if key not in seen_entries:
            seen_entries.add(key)
            collection = entry.get('collection', 'unknown')
            summary += f"<li><strong>Collection: {collection}</strong><ul>"
            for key, value in entry.items():
                if key != 'collection' and value:  # Skip empty values
                    summary += f"<li>{key.replace('_', ' ').title()}: {value}</li>"
            summary += "</ul></li>"

    # Statistics
    stats = {
        "Persons": len([n for n in graph.nodes if graph.nodes[n].get('type') == 'name']),
        "Phones": len([n for n in graph.nodes if graph.nodes[n].get('type') == 'phone']),
        "Emails": len([n for n in graph.nodes if graph.nodes[n].get('type') == 'email']),
        "Addresses": len([n for n in graph.nodes if graph.nodes[n].get('type') == 'address'])
    }

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Chan Graph Report</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.js"></script>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis-network.min.css" rel="stylesheet" type="text/css"/>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&display=swap');
            body {{
                background-color: #0A0F1A;
                color: #FFFFFF;
                font-family: 'Orbitron', sans-serif;
                margin: 0;
                padding: 0;
                overflow-x: hidden;
            }}
            .container {{
                display: flex;
                max-width: 1400px;
                margin: 20px auto;
            }}
            #network {{
                width: 75%;
                height: 800px;
                border: 2px solid #FFA500;
                background-color: #0A0F1A;
                box-shadow: 0 0 20px #00FFFF;
            }}
            .sidebar {{
                width: 25%;
                padding: 20px;
                background-color: #1C2526;
                border: 2px solid #00FFFF;
                box-shadow: 0 0 15px #00FFFF;
                overflow-y: auto;
                max-height: 800px;
            }}
            h1 {{
                color: #FFA500;
                text-align: center;
                text-shadow: 0 0 10px #00FFFF;
                margin-bottom: 20px;
            }}
            h2 {{
                color: #00FFFF;
                text-shadow: 0 0 5px #0000FF;
            }}
            ul {{
                list-style: none;
                padding: 0;
            }}
            li {{
                margin: 10px 0;
                color: #FFFFFF;
            }}
            .sidebar strong {{
                color: #FFA500;
            }}
            .stats {{
                margin-top: 20px;
                border-top: 1px solid #00FFFF;
                padding-top: 10px;
            }}
            .stats li {{
                display: flex;
                justify-content: space-between;
            }}
            .legend {{
                position: absolute;
                top: 20px;
                right: 20px;
                background: rgba(28, 37, 38, 0.9);
                padding: 10px;
                border-radius: 5px;
                box-shadow: 0 0 10px #00FFFF;
            }}
            .legend ul {{
                list-style: none;
                padding: 0;
            }}
            .legend li {{
                display: flex;
                align-items: center;
                margin: 5px 0;
            }}
            .legend span {{
                width: 15px;
                height: 15px;
                margin-right: 10px;
                display: inline-block;
            }}
            @media (max-width: 768px) {{
                .container {{
                    flex-direction: column;
                }}
                #network, .sidebar {{
                    width: 100%;
                }}
                .legend {{
                    position: static;
                    margin-top: 20px;
                }}
            }}
        </style>
    </head>
    <body>
        <h1>Chan Graph Report</h1>
        <div class="container">
            <div id="network"></div>
            <div class="sidebar">
                {summary}
                <div class="stats">
                    <h2>Statistics</h2>
                    <ul>
                        <li>Persons: {stats['Persons']}</li>
                        <li>Phones: {stats['Phones']}</li>
                        <li>Emails: {stats['Emails']}</li>
                        <li>Addresses: {stats['Addresses']}</li>
                    </ul>
                </div>
            </div>
        </div>
        <div class="legend">
            <h3>Legend</h3>
            <ul>
                <li><span style="background: #FFA500;"></span> Person/Name</li>
                <li><span style="background: #0000FF;"></span> Phone</li>
                <li><span style="background: #800080;"></span> Email</li>
                <li><span style="background: #008000;"></span> Address</li>
                <li><span style="background: #FF4500;"></span> ID</li>
                <li><span style="background: #FFFFFF;"></span> Misc</li>
            </ul>
        </div>
        <script>
            var nodes = new vis.DataSet({json.dumps(nodes)});
            var edges = new vis.DataSet({json.dumps(edges)});
            var container = document.getElementById('network');
            var data = {{ nodes: nodes, edges: edges }};
            var options = {{
                nodes: {{
                    font: {{ color: '#FFFFFF', face: 'Orbitron', size: 14 }},
                    borderWidth: 2,
                    shadow: {{ enabled: true, color: '#00FFFF', size: 10 }}
                }},
                edges: {{
                    width: 1.5,
                    shadow: {{ enabled: true, color: '#FF4500' }},
                    smooth: {{ type: 'curvedCW', roundness: 0.2 }}
                }},
                physics: {{
                    forceAtlas2Based: {{
                        gravitationalConstant: -150,
                        centralGravity: 0.005,
                        springLength: 200,
                        damping: 0.9
                    }},
                    maxVelocity: 50,
                    solver: 'forceAtlas2Based',
                    stabilization: {{ iterations: 1000 }}
                }},
                groups: {{
                    0: {{ color: {{ background: '#FFA500' }}, shape: 'dot' }},
                    1: {{ color: {{ background: '#0000FF' }} }},
                    2: {{ color: {{ background: '#800080' }} }},
                    3: {{ color: {{ background: '#008000' }} }},
                    4: {{ color: {{ background: '#FF4500' }} }}
                }},
                interaction: {{
                    hover: true,
                    tooltipDelay: 100,
                    zoomView: true,
                    dragNodes: true
                }}
            }};
            var network = new vis.Network(container, data, options);
            network.on("stabilizationIterationsDone", function () {{
                network.setOptions({{ physics: false }});
            }});
        </script>
    </body>
    </html>
    """
    return html_content

# Telegram bot handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send me a text message with data or upload a .txt or .pdf file to generate a Chan Graph report.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    data = parse_text(text)
    graph = create_graph(data)
    html_content = generate_html_report(graph, data)
    
    # Save HTML report
    report_path = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # Send report to user
    with open(report_path, 'rb') as f:
        await update.message.reply_document(document=f, filename="Chan_graph_report.html")
    
    # Clean up
    os.remove(report_path)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    file = await document.get_file()
    file_stream = BytesIO()
    await file.download_to_memory(file_stream)
    file_stream.seek(0)

    if document.file_name.endswith('.pdf'):
        data = parse_pdf(file_stream)
    elif document.file_name.endswith('.txt'):
        data = parse_txt(file_stream)
    else:
        await update.message.reply_text("Please upload a .txt or .pdf file.")
        return

    graph = create_graph(data)
    html_content = generate_html_report(graph, data)
    
    # Save HTML report
    report_path = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # Send report to user
    with open(report_path, 'rb') as f:
        await update.message.reply_document(document=f, filename="Chan_graph_report.html")
    
    # Clean up
    os.remove(report_path)

def main():
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set. Please set it in your .env file or environment.")
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.run_polling()

if __name__ == '__main__':
    main()