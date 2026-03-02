# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import argparse
import random
import sys
import os
import mimetypes
import re
import traceback
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('application/javascript', '.mjs')

import flask
from flask import request, session, jsonify, Blueprint, current_app, Response, stream_with_context
import logging

import json
import html
import pandas as pd

from data_formulator.agents.agent_concept_derive import ConceptDeriveAgent
from data_formulator.agents.agent_py_concept_derive import PyConceptDeriveAgent

from data_formulator.agents.agent_py_data_transform import PythonDataTransformationAgent
from data_formulator.agents.agent_sql_data_transform import SQLDataTransformationAgent
from data_formulator.agents.agent_py_data_rec import PythonDataRecAgent
from data_formulator.agents.agent_sql_data_rec import SQLDataRecAgent

from data_formulator.agents.agent_sort_data import SortDataAgent
from data_formulator.agents.agent_data_load import DataLoadAgent
from data_formulator.agents.agent_data_clean import DataCleanAgent
from data_formulator.agents.agent_data_clean_stream import DataCleanAgentStream
from data_formulator.agents.agent_code_explanation import CodeExplanationAgent
from data_formulator.agents.agent_interactive_explore import InteractiveExploreAgent
from data_formulator.agents.agent_report_gen import ReportGenAgent
from data_formulator.agents.client_utils import Client
from data_formulator.model_registry import model_registry

from data_formulator.db_manager import db_manager
from data_formulator.workflows.exploration_flow import run_exploration_flow_streaming

# Get logger for this module (logging config done in app.py)
logger = logging.getLogger(__name__)

agent_bp = Blueprint('agent', __name__, url_prefix='/api/agent')

def get_client(model_config):
    # For global models, resolve real credentials from the server-side registry.
    # The frontend only knows the model id; the api_key never leaves the server.
    if model_config.get("is_global"):
        real_config = model_registry.get_config(model_config["id"])
        if real_config:
            model_config = real_config

    for key in model_config:
        if isinstance(model_config[key], str):
            model_config[key] = model_config[key].strip()

    client = Client(
        model_config["endpoint"],
        model_config["model"],
        model_config.get("api_key") or None,
        html.escape(model_config["api_base"]) if model_config.get("api_base") else None,
        model_config.get("api_version") or None,
    )

    return client


@agent_bp.route('/check-available-models', methods=['GET', 'POST'])
def check_available_models():
    """
    Return all globally configured models with their connectivity status.

    Previously only reachable models were returned, causing the frontend to
    silently omit unreachable entries.  Now every configured model is included
    so the frontend can show a clear connected / disconnected indicator.
    Sensitive credentials (api_key) are never sent to the client.
    """
    results = []

    for public_info in model_registry.list_public():
        full_config = model_registry.get_config(public_info["id"])
        status = "disconnected"
        error = None

        try:
            client = get_client(full_config)
            response = client.get_completion(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Respond 'I can hear you.' if you can hear me."},
                ]
            )
            if "I can hear you." in response.choices[0].message.content:
                status = "connected"
        except Exception as e:
            # Log the full error server-side (may contain credentials) but only
            # send a generic message to the frontend so that API keys embedded
            # in provider error responses are never leaked to end users.
            logger.warning(f"Model connectivity check failed for {public_info['id']}: {e}")
            error = "无法连接，请联系管理员检查服务端配置"

        results.append({**public_info, "status": status, "error": error})

    return json.dumps(results)

def sanitize_model_error(error_message: str) -> str:
    """Sanitize model API error messages before sending to client."""
    # HTML escape the message
    message = html.escape(error_message)
    
    # Remove any potential API keys that might be in the error
    message = re.sub(r'(api[-_]?key|api[-_]?token)[=:]\s*[^\s&]+', r'\1=<redacted>', message, flags=re.IGNORECASE)
    
    # Keep only the essential error info
    if len(message) > 500:  # Truncate very long messages
        message = message[:500] + "..."
        
    return message

@agent_bp.route('/test-model', methods=['GET', 'POST'])
def test_model():
    if request.is_json:
        logger.info("# code query: ")
        content = request.get_json()

        # contains endpoint, key, model, api_base, api_version
        logger.info("content------------------------------")
        logger.info(content)

        client = get_client(content['model'])
        
        try:
            response = client.get_completion(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Respond 'I can hear you.' if you can hear me. Do not say anything other than 'I can hear you.'"},
                ]
            )

            logger.info(f"model: {content['model']}")
            logger.info(f"welcome message: {response.choices[0].message.content}")

            if "I can hear you." in response.choices[0].message.content:
                result = {
                    "model": content['model'],
                    "status": 'ok',
                    "message": ""
                }
        except Exception as e:
            logger.warning(f"Error testing model {content['model'].get('id', '')}: {e}")
            is_global = content['model'].get('is_global', False)
            result = {
                "model": content['model'],
                "status": 'error',
                "message": "无法连接，请联系管理员检查服务端配置" if is_global
                           else sanitize_model_error(str(e)),
            }
    else:
        result = {'status': 'error'}
    
    return json.dumps(result)

@agent_bp.route('/process-data-on-load', methods=['GET', 'POST'])
def process_data_on_load_request():

    if request.is_json:
        logger.info("# process data query: ")
        content = request.get_json()
        token = content["token"]

        client = get_client(content['model'])

        logger.info(f" model: {content['model']}")

        try:
            conn = db_manager.get_connection(session['session_id'])
        except Exception as e:
            conn = None

        agent = DataLoadAgent(client=client, conn=conn)
        
        candidates = agent.run(content["input_data"])
        
        candidates = [c['content'] for c in candidates if c['status'] == 'ok']

        response = flask.jsonify({ "status": "ok", "token": token, "result": candidates })
    else:
        response = flask.jsonify({ "token": -1, "status": "error", "result": [] })

    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


@agent_bp.route('/derive-concept-request', methods=['GET', 'POST'])
def derive_concept_request():

    if request.is_json:
        logger.info("# code query: ")
        content = request.get_json()
        token = content["token"]

        client = get_client(content['model'])

        logger.info(f" model: {content['model']}")
        agent = ConceptDeriveAgent(client=client)

        candidates = agent.run(content["input_data"], [f['name'] for f in content["input_fields"]], 
                                       content["output_name"], content["description"])
        
        candidates = [c['code'] for c in candidates if c['status'] == 'ok']

        response = flask.jsonify({ "status": "ok", "token": token, "result": candidates })
    else:
        response = flask.jsonify({ "token": -1, "status": "error", "result": [] })

    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


@agent_bp.route('/derive-py-concept', methods=['GET', 'POST'])
def derive_py_concept():

    if request.is_json:
        logger.info("# code query: ")
        content = request.get_json()
        token = content["token"]

        client = get_client(content['model'])

        logger.info(f" model: {content['model']}")
        agent = PyConceptDeriveAgent(client=client)

        results = agent.run(content["input_data"], [f['name'] for f in content["input_fields"]], 
                                       content["output_name"], content["description"])
        
        response = flask.jsonify({ "status": "ok", "token": token, "results": results })
    else:
        response = flask.jsonify({ "token": -1, "status": "error", "results": [] })

    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

@agent_bp.route('/clean-data', methods=['GET', 'POST'])
def clean_data_request():

    if request.is_json:
        logger.info("# data clean request")
        content = request.get_json()
        token = content["token"]

        client = get_client(content['model'])

        logger.info(f" model: {content['model']}")
        
        agent = DataCleanAgent(client=client)

        try:
            candidates = agent.run(content.get('prompt', ''), content.get('artifacts', []), content.get('dialog', []))
        except Exception as e:
            logger.error(e)
            if 'unable to download html from url' in str(e):
                return flask.jsonify({ "token": token, "status": "error", "result":  'this website doesn\'t allow us to download html from url :(' })
            else:
                return flask.jsonify({ "token": token, "status": "error", "result": 'unable to process data clean request' })

        
        candidates = [c for c in candidates if c['status'] == 'ok']

        response = flask.jsonify({ "status": "ok", "token": token, "result": candidates })
    else:
        response = flask.jsonify({ "token": -1, "status": "error", "result": [] })

    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


@agent_bp.route('/clean-data-stream', methods=['GET', 'POST'])
def clean_data_stream_request():
    def generate():
        if request.is_json:
            logger.info("# data clean stream request")
            content = request.get_json()
            token = content["token"]

            client = get_client(content['model'])

            logger.info(f" model: {content['model']}")
            
            agent = DataCleanAgentStream(client=client)

            try:
                for chunk in agent.stream(content.get('prompt', ''), content.get('artifacts', []), content.get('dialog', [])):
                    yield chunk
            except Exception as e:
                logger.error(e)
                if 'unable to download html from url' in str(e):
                    error_data = { 
                        "token": token, 
                        "status": "error", 
                        "result": 'this website doesn\'t allow us to download html from url :(' 
                    }
                else:
                    error_data = { 
                        "token": token, 
                        "status": "error", 
                        "result": 'unable to process data clean request' 
                    }
                yield '\n' + json.dumps(error_data) + '\n'
        else:
            error_data = { 
                "token": -1, 
                "status": "error", 
                "result": "Invalid request format" 
            }
            yield '\n' + json.dumps(error_data) + '\n'

    response = Response(
        stream_with_context(generate()),
        mimetype='application/json',
        headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        }
    )
    return response


@agent_bp.route('/sort-data', methods=['GET', 'POST'])
def sort_data_request():

    if request.is_json:
        logger.info("# sort query: ")
        content = request.get_json()
        token = content["token"]

        client = get_client(content['model'])

        agent = SortDataAgent(client=client)
        candidates = agent.run(content['field'], content['items'])

        candidates = candidates if candidates != None else []
        response = flask.jsonify({ "status": "ok", "token": token, "result": candidates })
    else:
        response = flask.jsonify({ "token": -1, "status": "error", "result": [] })

    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

@agent_bp.route('/derive-data', methods=['GET', 'POST'])
def derive_data():
    token = ""
    conn = None

    if request.is_json:
        try:
            logger.info("# request data: ")
            content = request.get_json()
            token = content["token"]

            client = get_client(content['model'])

            # each table is a dict with {"name": xxx, "rows": [...]}
            input_tables = content["input_tables"]
            chart_type = content.get("chart_type", "")
            chart_encodings = content.get("chart_encodings", {})

            instruction = content["extra_prompt"]
            language = content.get("language", "python")  # whether to use sql or python, default to python
            max_repair_attempts = content.get("max_repair_attempts", 1)
            agent_coding_rules = content.get("agent_coding_rules", "")
            prev_messages = content.get("additional_messages", [])

            logger.info("== input tables ===>")
            for table in input_tables:
                logger.info(f"===> Table: {table['name']} (first 5 rows)")
                logger.info(table['rows'][:5])

            logger.info("== user spec ===")
            logger.info(chart_type)
            logger.info(chart_encodings)
            logger.info(instruction)

            mode = "transform"
            if chart_encodings == {}:
                mode = "recommendation"

            conn = db_manager.get_connection(session['session_id']) if language == "sql" else None

            if mode == "recommendation":
                agent = SQLDataRecAgent(client=client, conn=conn, agent_coding_rules=agent_coding_rules) if language == "sql" else PythonDataRecAgent(client=client, exec_python_in_subprocess=current_app.config['CLI_ARGS']['exec_python_in_subprocess'], agent_coding_rules=agent_coding_rules)
                results = agent.run(input_tables, instruction, n=1, prev_messages=prev_messages)
            else:
                agent = SQLDataTransformationAgent(client=client, conn=conn, agent_coding_rules=agent_coding_rules) if language == "sql" else PythonDataTransformationAgent(client=client, exec_python_in_subprocess=current_app.config['CLI_ARGS']['exec_python_in_subprocess'], agent_coding_rules=agent_coding_rules)
                results = agent.run(input_tables, instruction, chart_type, chart_encodings, prev_messages)

            repair_attempts = 0
            while (
                isinstance(results, list)
                and len(results) > 0
                and results[0].get('status') in ('error', 'sql_error', 'other error')
                and repair_attempts < max_repair_attempts
            ):  # try up to n times
                error_message = results[0].get('content', 'Unknown error')
                new_instruction = f"We run into the following problem executing the code, please fix it:\n\n{error_message}\n\nPlease think step by step, reflect why the error happens and fix the code so that no more errors would occur."
                prev_dialog = results[0].get('dialog', [])

                try:
                    if mode == "transform":
                        results = agent.followup(input_tables, prev_dialog, [], chart_type, chart_encodings, new_instruction, n=1)
                    if mode == "recommendation":
                        results = agent.followup(input_tables, prev_dialog, [], new_instruction, n=1)
                except Exception as followup_exc:
                    logger.exception("derive_data followup failed")
                    results = [{
                        "status": "error",
                        "content": sanitize_model_error(str(followup_exc)),
                        "code": "",
                        "dialog": [],
                    }]
                    break

                repair_attempts += 1

            # If SQL path is still failing after repair attempts, fallback to
            # Python mode once to improve robustness for non-ASCII identifiers.
            if (
                language == "sql"
                and isinstance(results, list)
                and len(results) > 0
                and results[0].get('status') in ('error', 'sql_error', 'other error')
            ):
                logger.warning("SQL derive_data still failing after retries; fallback to python mode")
                try:
                    if mode == "recommendation":
                        py_agent = PythonDataRecAgent(
                            client=client,
                            exec_python_in_subprocess=current_app.config['CLI_ARGS']['exec_python_in_subprocess'],
                            agent_coding_rules=agent_coding_rules,
                        )
                        py_results = py_agent.run(input_tables, instruction, n=1, prev_messages=prev_messages)
                    else:
                        py_agent = PythonDataTransformationAgent(
                            client=client,
                            exec_python_in_subprocess=current_app.config['CLI_ARGS']['exec_python_in_subprocess'],
                            agent_coding_rules=agent_coding_rules,
                        )
                        py_results = py_agent.run(input_tables, instruction, chart_type, chart_encodings, prev_messages)

                    if isinstance(py_results, list) and len(py_results) > 0:
                        for item in py_results:
                            if isinstance(item, dict):
                                item["fallback_from_sql"] = True
                        results = py_results
                except Exception as fallback_exc:
                    logger.warning("Python fallback failed: %s", fallback_exc, exc_info=True)

            response = flask.jsonify({ "token": token, "status": "ok", "results": results })
        except Exception as exc:
            logger.exception("derive_data request failed")
            response = flask.jsonify({
                "token": token,
                "status": "error",
                "results": [{
                    "status": "error",
                    "content": sanitize_model_error(str(exc)),
                    "code": "",
                    "dialog": [],
                }],
            })
        finally:
            if conn:
                conn.close()
    else:
        response = flask.jsonify({ "token": "", "status": "error", "results": [] })

    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

@agent_bp.route('/explore-data-streaming', methods=['GET', 'POST'])
def explore_data_streaming():
    def generate():
        if request.is_json:
            logger.setLevel(logging.INFO)

            logger.info("# explore data request: ")
            content = request.get_json()        
            token = content["token"]

            # each table is a dict with {"name": xxx, "rows": [...]}
            input_tables = content["input_tables"]
            initial_plan = content["initial_plan"]  # The exploration question
            language = content.get("language", "python")  # whether to use sql or python, default to python
            max_iterations = content.get("max_iterations", 3)  # Number of exploration iterations
            max_repair_attempts = content.get("max_repair_attempts", 1)
            agent_exploration_rules = content.get("agent_exploration_rules", "")
            agent_coding_rules = content.get("agent_coding_rules", "")

            logger.info("== input tables ===>")
            for table in input_tables:
                logger.info(f"===> Table: {table['name']} (first 5 rows)")
                logger.info(table['rows'][:5])

            logger.info("== exploration question ===")
            logger.info(initial_plan)

            # Model config for the exploration flow.
            # For global models, resolve real credentials from the server-side
            # registry so that api_key is never sent by the frontend.
            raw_model = content['model']
            if raw_model.get('is_global'):
                resolved = model_registry.get_config(raw_model.get('id', ''))
                model_config = resolved if resolved else raw_model
            else:
                model_config = {
                    "endpoint": raw_model["endpoint"],
                    "model": raw_model["model"],
                    "api_key": raw_model.get("api_key", ""),
                    "api_base": raw_model.get("api_base", ""),
                    "api_version": raw_model.get("api_version", ""),
                }

            session_id = session.get('session_id') if language == "sql" else None
            exec_python_in_subprocess = current_app.config['CLI_ARGS']['exec_python_in_subprocess']

            try:
                for result in run_exploration_flow_streaming(
                    model_config=model_config,
                    input_tables=input_tables,
                    initial_plan=initial_plan,
                    language=language,
                    session_id=session_id,
                    exec_python_in_subprocess=exec_python_in_subprocess,
                    max_iterations=max_iterations,
                    max_repair_attempts=max_repair_attempts,
                    agent_exploration_rules=agent_exploration_rules,
                    agent_coding_rules=agent_coding_rules
                ):
                    response_data = { 
                        "token": token, 
                        "status": "ok", 
                        "result": result 
                    }
                    
                    yield json.dumps(response_data) + '\n'
                    
                    # Break if we get a completion result
                    if result.get("type") == "completion":
                        break
            
            except Exception as e:
                logger.setLevel(logging.WARNING)
                logger.error(f"Error in exploration flow: {e}")
                logger.error(traceback.format_exc())
                error_data = { 
                    "token": token, 
                    "status": "error", 
                    "result": None,
                    "error_message": str(e)
                }
                yield json.dumps(error_data) + '\n'
            
            logger.setLevel(logging.WARNING)

        else:
            error_data = { 
                "token": "", 
                "status": "error", 
                "result": None,
                "error_message": "Invalid request format"
            }
            yield json.dumps(error_data) + '\n'

    response = Response(
        stream_with_context(generate()),
        mimetype='application/json',
        headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        }
    )
    return response


@agent_bp.route('/refine-data', methods=['GET', 'POST'])
def refine_data():

    if request.is_json:
        logger.info("# request data: ")
        content = request.get_json()        
        token = content["token"]


        client = get_client(content['model'])

        # each table is a dict with {"name": xxx, "rows": [...]}
        input_tables = content["input_tables"]
        dialog = content["dialog"]

        chart_type = content.get("chart_type", "")
        chart_encodings = content.get("chart_encodings", {})

        new_instruction = content["new_instruction"]
        latest_data_sample = content["latest_data_sample"]
        max_repair_attempts = content.get("max_repair_attempts", 1)
        agent_coding_rules = content.get("agent_coding_rules", "")
        
        language = content.get("language", "python") # whether to use sql or python, default to python

        logger.info("== input tables ===>")
        for table in input_tables:
            logger.info(f"===> Table: {table['name']} (first 5 rows)")
            logger.info(table['rows'][:5])
        
        logger.info("== user spec ===>")
        logger.info(chart_type)
        logger.info(chart_encodings)
        logger.info(new_instruction)

        conn = db_manager.get_connection(session['session_id']) if language == "sql" else None

        # always resort to the data transform agent       
        agent = SQLDataTransformationAgent(client=client, conn=conn, agent_coding_rules=agent_coding_rules) if language == "sql" else PythonDataTransformationAgent(client=client, exec_python_in_subprocess=current_app.config['CLI_ARGS']['exec_python_in_subprocess'], agent_coding_rules=agent_coding_rules)
        results = agent.followup(input_tables, dialog, latest_data_sample, chart_type, chart_encodings, new_instruction, n=1)

        repair_attempts = 0
        while results[0]['status'] == 'error' and repair_attempts < max_repair_attempts: # only try once
            error_message = results[0]['content']
            new_instruction = f"We run into the following problem executing the code, please fix it:\n\n{error_message}\n\nPlease think step by step, reflect why the error happens and fix the code so that no more errors would occur."
            prev_dialog = results[0]['dialog']

            results = agent.followup(input_tables, prev_dialog, [], chart_type, chart_encodings, new_instruction, n=1)
            repair_attempts += 1

        if conn:
            conn.close()

        response = flask.jsonify({ "token": token, "status": "ok", "results": results})
    else:
        response = flask.jsonify({ "token": "", "status": "error", "results": []})

    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

@agent_bp.route('/code-expl', methods=['GET', 'POST'])
def request_code_expl():
    if request.is_json:
        logger.info("# request data: ")
        content = request.get_json()        
        client = get_client(content['model'])

        # each table is a dict with {"name": xxx, "rows": [...]}
        input_tables = content["input_tables"]
        code = content["code"]
        
        code_expl_agent = CodeExplanationAgent(client=client)
        candidates = code_expl_agent.run(input_tables, code)
        
        # Return the first candidate's content as JSON
        if candidates and len(candidates) > 0:
            result = candidates[0]
            if result['status'] == 'ok':
                return jsonify(result)
            else:
                return jsonify(result), 400
        else:
            return jsonify({'error': 'No explanation generated'}), 400
    else:
        return jsonify({'error': 'Invalid request format'}), 400

@agent_bp.route('/get-recommendation-questions', methods=['GET', 'POST'])
def get_recommendation_questions():
    def generate():
        if request.is_json:
            logger.info("# get recommendation questions request")
            content = request.get_json()
            token = content.get("token", "")

            client = get_client(content['model'])

            language = content.get("language", "python")
            db_conn = None
            if language == "sql":
                try:
                    db_conn = db_manager.get_connection(session['session_id'])
                except Exception as conn_exc:
                    logger.warning("get-recommendation-questions: failed to get SQL conn, falling back to python: %s", conn_exc)

            agent_exploration_rules = content.get("agent_exploration_rules", "")

            # Get input tables from the request
            input_tables = content.get("input_tables", [])

            # Get exploration thread if provided (for context from previous explorations)
            mode = content.get("mode", "interactive")
            start_question = content.get("start_question", None)
            exploration_thread = content.get("exploration_thread", None)
            current_chart = content.get("current_chart", None)
            current_data_sample = content.get("current_data_sample", None)

            agent = InteractiveExploreAgent(
                client=client,
                agent_exploration_rules=agent_exploration_rules,
                db_conn=db_conn,
            )

            try:
                for chunk in agent.run(
                    input_tables, start_question, exploration_thread,
                    current_data_sample, current_chart, mode,
                ):
                    yield chunk
            except Exception as e:
                logger.warning(
                    "get-recommendation-questions SQL agent failed (%s); retrying with python mode", e
                )
                # SQL mode failed (often non-ASCII identifiers) — retry without DB connection.
                if language == "sql" and db_conn is not None:
                    try:
                        if db_conn:
                            try:
                                db_conn.close()
                            except Exception:
                                pass
                        py_agent = InteractiveExploreAgent(
                            client=client,
                            agent_exploration_rules=agent_exploration_rules,
                            db_conn=None,
                        )
                        for chunk in py_agent.run(
                            input_tables, start_question, exploration_thread,
                            current_data_sample, current_chart, mode,
                        ):
                            yield chunk
                        return
                    except Exception as py_exc:
                        logger.error(
                            "get-recommendation-questions python fallback also failed: %s", py_exc
                        )
                        error_data = {"content": sanitize_model_error(str(py_exc))}
                        yield 'error: ' + json.dumps(error_data) + '\n'
                        return

                error_data = {"content": sanitize_model_error(str(e))}
                yield 'error: ' + json.dumps(error_data) + '\n'
        else:
            error_data = {"content": "Invalid request format"}
            yield 'error: ' + json.dumps(error_data) + '\n'

    response = Response(
        stream_with_context(generate()),
        mimetype='application/json',
        headers={ 'Access-Control-Allow-Origin': '*',  }
    )
    return response

@agent_bp.route('/generate-report-stream', methods=['GET', 'POST'])
def generate_report_stream():
    def generate():
        if request.is_json:
            logger.info("# generate report stream request")
            content = request.get_json()
            token = content.get("token", "")

            client = get_client(content['model'])

            language = content.get("language", "python")
            if language == "sql":
                db_conn = db_manager.get_connection(session['session_id'])
            else:
                db_conn = None

            agent_exploration_rules = content.get("agent_exploration_rules", "")
            agent_coding_rules = content.get("agent_coding_rules", "")
            ui_language = content.get("ui_language", "en")

            agent = ReportGenAgent(client=client, conn=db_conn,
                                   agent_exploration_rules=agent_exploration_rules,
                                   agent_coding_rules=agent_coding_rules,
                                   ui_language=ui_language)

            # Get input tables and charts from the request
            input_tables = content.get("input_tables", [])
            charts = content.get("charts", [])
            style = content.get("style", "blog post")

            try:
                for chunk in agent.stream(input_tables, charts, style):
                    yield chunk
            except Exception as e:
                logger.error(e)
                error_data = { 
                    "content": "unable to process report generation request" 
                }
                yield 'error: ' + json.dumps(error_data) + '\n'
        else:
            error_data = { 
                "content": "Invalid request format" 
            }
            yield 'error: ' + json.dumps(error_data) + '\n'

    response = Response(
        stream_with_context(generate()),
        mimetype='application/json',
        headers={ 'Access-Control-Allow-Origin': '*',  }
    )
    return response


@agent_bp.route('/refresh-derived-data', methods=['POST'])
def refresh_derived_data():
    """
    Re-run Python transformation code with new input data to refresh a derived table.
    
    This endpoint takes:
    - input_tables: list of {name: string, rows: list} objects representing the parent tables
    - code: the Python transformation code to execute
    
    Returns:
    - status: 'ok' or 'error'
    - rows: the resulting rows if successful
    - message: error message if failed
    """
    try:
        from data_formulator.py_sandbox import run_transform_in_sandbox2020
        from flask import current_app
        
        data = request.get_json()
        input_tables = data.get('input_tables', [])
        code = data.get('code', '')
        
        if not input_tables:
            return jsonify({
                "status": "error",
                "message": "No input tables provided"
            }), 400
            
        if not code:
            return jsonify({
                "status": "error", 
                "message": "No transformation code provided"
            }), 400
        
        # Convert input tables to pandas DataFrames
        df_list = []
        for table in input_tables:
            table_name = table.get('name', '')
            table_rows = table.get('rows', [])
            
            if not table_rows:
                return jsonify({
                    "status": "error",
                    "message": f"Table '{table_name}' has no rows"
                }), 400
                
            df = pd.DataFrame.from_records(table_rows)
            df_list.append(df)
        
        # Get exec_python_in_subprocess setting from app config
        exec_python_in_subprocess = current_app.config.get('CLI_ARGS', {}).get('exec_python_in_subprocess', False)
        
        # Run the transformation code
        result = run_transform_in_sandbox2020(code, df_list, exec_python_in_subprocess)
        
        if result['status'] == 'ok':
            result_df = result['content']
            
            # Convert result DataFrame to list of records
            rows = json.loads(result_df.to_json(orient='records', date_format='iso'))
            
            return jsonify({
                "status": "ok",
                "rows": rows,
                "message": "Successfully refreshed derived data"
            })
        else:
            return jsonify({
                "status": "error",
                "message": result.get('content', 'Unknown error during transformation')
            }), 400
            
    except Exception as e:
        logger.error(f"Error refreshing derived data: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400
