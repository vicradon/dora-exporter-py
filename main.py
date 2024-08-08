from flask import Flask, request, jsonify
import datetime
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from prometheus_client import make_wsgi_app
from prometheus_client import Gauge, Summary, Histogram, Info, Enum, Counter
from time import sleep, time, mktime, strptime
import threading
import random
from dotenv import load_dotenv
import json
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    '/metrics': make_wsgi_app()
})

@app.route('/')
def index():
    return "GitHub Webhook Listener"

@app.route('/github/webhook', methods=['POST'])
def webhook():
    event_type = request.headers.get('X-GitHub-Event')
    
    if event_type == 'push':
        handle_commit_event(request.json)
    elif event_type == 'issues':
        handle_issue_event(request.json)
    elif event_type == 'pull_request':
        handle_pull_request_event(request.json)
    elif event_type == 'status':
        handle_status_event(request.json)
    else:
        print(event_type)
        return jsonify({'message': 'Event not supported'}), 202
    
    return jsonify({'message': 'Event received'}), 200


github_deployment_count = Counter("github_deployments_total", "Total GitHub deployments per repo, per environment, per branch", ["state", "environment", "repository", "branch"])
github_deployment_duration = Gauge("github_deployments_duration_seconds", "Duration of deployments in seconds", ["state", "environment", "repository", "branch"])
github_deployment_failures = Counter("github_deployments_failures_total", "Total failed GitHub deployments per repo, per environment, per branch", ["environment", "repository", "branch"])
mttr_histogram = Histogram("mttr_seconds", "Mean Time to Recovery (MTTR) in seconds", ["environment", "repository", "branch"])
lead_time_histogram = Histogram("lead_time_seconds", "Lead Time for Changes in seconds", ["repository", "branch"])

pending_deployments = {}
failure_start_times = {}
commit_times = {}

def handle_status_event(payload):
    print("STATUS EVENT")

    state = payload["state"]
    environment = payload["context"]
    repo = payload["repository"]["name"]
    branch = payload["branches"][0]["name"]
    commit_id = payload["commit"]["sha"]

    github_deployment_count.labels(state, environment, repo, branch).inc()
    
    # created_at = datetime.datetime.fromisoformat(payload["created_at"].replace("Z", "+00:00"))
    # updated_at = datetime.datetime.fromisoformat(payload["updated_at"].replace("Z", "+00:00"))
    # duration = (updated_at - created_at).total_seconds()

    event_time = datetime.datetime.fromisoformat(payload["created_at"].replace("Z", "+00:00"))


    deployment_key = (environment, repo, branch)

    if state == "pending":
        # Store the start time for pending deployments
        pending_deployments[deployment_key] = event_time
        logging.info(f"Pending deployment for {deployment_key} started at {event_time}")
    elif state in ["success", "failure"]:
        if deployment_key in pending_deployments:
            start_time = pending_deployments.pop(deployment_key)
            duration = (event_time - start_time).total_seconds()
            github_deployment_duration.labels(environment, repo, branch).set(duration)
            logging.info(f"Deployment for {deployment_key} ended at {event_time} with state {state}. Duration: {duration} seconds")

        github_deployment_count.labels(state, environment, repo, branch).inc()


        # Increment the failure count if the state is "failure" for calculating change failure rate
        if state == "failure":
            github_deployment_failures.labels(environment, repo, branch).inc()

        # Check for recovery from a previous failure
        if deployment_key in failure_start_times:
            failure_start_time = failure_start_times.pop(deployment_key)
            recovery_time = (event_time - failure_start_time).total_seconds()
            mttr_histogram.labels(environment, repo, branch).observe(recovery_time)
            logging.info(f"Recovered deployment for {deployment_key} at {event_time}. Recovery time: {recovery_time} seconds")

        # Calculate lead time for changes if commit_id is provided
        if commit_id:
            commit_key = (repo, branch, commit_id)
            if commit_key in commit_times:
                commit_time = commit_times.pop(commit_key)
                lead_time = (event_time - commit_time).total_seconds()
                lead_time_histogram.labels(repo, branch).observe(lead_time)
                logging.info(f"Lead time for commit {commit_id} to deployment for {repo}/{branch}: {lead_time} seconds")

    # json_string = json.dumps(payload, indent=4)
    # current_timestamp = time()
    # with open(f'status_event-{current_timestamp}', 'w') as file:
    #     file.write(json_string)

def handle_commit_event(payload):
    print("COMMIT EVENT")

    commit_id = None
    repo = payload["repository"]["name"]
    branch = None
    commit_date = None
    commit_time = None

    if "head_commit" in payload:
        commit_id = payload["head_commit"]["id"]
        commit_date = payload["head_commit"]["timestamp"]
        commit_time = datetime.datetime.fromisoformat(commit_date.replace("Z", "+00:00"))

    if "branches" in payload:
        branch = payload["branches"][0]["name"]

    commit_key = (repo, branch, commit_id)
    commit_times[commit_key] = commit_time
    logging.info(f"Commit {commit_id} for {repo}/{branch} recorded at {commit_time}")

    json_string = json.dumps(payload, indent=4)
    current_timestamp = time()
    with open(f'commit_event-{current_timestamp}', 'w') as file:
        file.write(json_string)

if __name__ == '__main__':
    app.run(port=5500, debug=True)
