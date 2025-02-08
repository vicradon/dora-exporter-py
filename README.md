# DORA Metrics Prometheus Exporter in Python

This Flask app implements the DevOps Research and Assessment (DORA) specifications. It's purpose is to collect metrics about application deployment so as to know how effective the deployment pipelines is for a DevOps team.

This application uses webhooks, placed on Github, to collect metrics whenever a deployment or commit is made. It sends these metrics to Prometheus for storage. The final intent is using Grafana to visualize these metrics to fully understand the overall health of the DevOps team and their processes.

The metrics being collected are:

1. Deployment Frequency - measures the frequency of success production releases, highlighting a team's agility
2. Lead Time for Changes - represents the average time it takes for a commit to go from a dev environment to production, highlighting a team's development speed
3. Change Failure Rate - calculates the percentage of deployments that cause production to break, hightlighting a team's quality of releases
4. Mean Time to Recovery (MTTR) - measures the average duration required to restore the application after a failure on production, accessing a team's responsiveness to incidents

