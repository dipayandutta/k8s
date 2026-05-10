# Kubernetes Demo Projects

A collection of containerized applications deployed on Kubernetes.

## Projects

### react-k8s-demo
A React app (Create React App) built with a multi-stage Docker image (Node.js builder → nginx:alpine) and deployed to Kubernetes.

**K8s resources:** Deployment, Service (NodePort 30000), ConfigMap, PersistentVolume, PersistentVolumeClaim

### python-flask-app
A Python Flask application deployed on Kubernetes.

## Quick Start

```bash
# Apply all manifests for the React app
kubectl apply -f react-k8s-demo/k8s/

# Check pod status
kubectl get pods

# Access the app
# http://localhost:30000
```

## Docker Image

```bash
# Build and push
docker build -t dipayandutta/k8s:react-v2 react-k8s-demo/
docker push dipayandutta/k8s:react-v2
```
