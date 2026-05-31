# Kubernetes Operators with Kubebuilder — Complete Learning Guide

> A step-by-step guide to building a Guestbook Operator from scratch, with full Go code and interview-ready Q&A.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [What is a Kubernetes Operator?](#what-is-a-kubernetes-operator)
3. [Project Setup](#step-1--project-setup)
4. [Create the API](#step-2--create-the-api)
5. [Define the CRD Schema](#step-3--define-the-crd-schema)
6. [Generate Manifests](#step-4--generate-crd-manifests)
7. [Write the Controller](#step-5--write-the-controller)
8. [Install and Run](#step-6--install-crds-and-run)
9. [Deploy Your Guestbook](#step-7--deploy-your-guestbook)
10. [Verify Everything Works](#step-8--verify-everything-works)
11. [Scale with the Operator](#step-9--scale-with-the-operator)
12. [Delete and Cleanup](#step-10--delete-and-cleanup)
13. [Interview Questions & Answers](#interview-questions--answers)

---

## Prerequisites

```bash
# Verify your kind cluster
kubectl get nodes

# Expected output:
# NAME                 STATUS   ROLES           AGE   VERSION
# kind-control-plane   Ready    control-plane   25h   v1.35.0
# kind-worker          Ready    <none>          25h   v1.35.0
# kind-worker2         Ready    <none>          25h   v1.35.0

# Verify kubebuilder
kubebuilder version

# Verify Go
go version
```

---

## What is a Kubernetes Operator?

An Operator is a Kubernetes extension that:
- Defines **Custom Resources** (your own Kubernetes objects)
- Runs a **Controller** that watches those resources
- **Reconciles** desired state with actual state — continuously and automatically

```
YOU declare what you want (Spec)
        ↓
Operator watches for changes
        ↓
Reconcile loop runs
        ↓
Operator creates/updates/deletes child resources
        ↓
Operator updates Status (what's actually running)
        ↓
Loop repeats if anything drifts
```

> **Analogy:** An Operator is like a human SRE encoded as software — it knows how to deploy, scale, heal, and clean up your application automatically.

---

## Step 1 — Project Setup

```bash
# Create project directory
mkdir guestbook && cd guestbook

# Initialize kubebuilder project
kubebuilder init --domain my.domain --repo my.domain/guestbook
```

### What gets generated

```
guestbook/
├── cmd/                    # main.go lives here — operator entrypoint
├── config/                 # All Kubernetes YAML manifests
│   ├── crd/                # CRD definitions (auto-generated)
│   ├── rbac/               # RBAC roles and bindings
│   └── manager/            # Deployment manifest for the operator
├── hack/                   # boilerplate.go.txt for license headers
├── test/                   # e2e and integration test scaffolding
├── Makefile                # make run, make deploy, make manifests
├── Dockerfile              # Container image for your operator
├── go.mod                  # Go module: my.domain/guestbook
└── go.sum                  # Dependency checksums (never edit manually)
```

### Understanding the flags

| Flag | Value | Effect |
|---|---|---|
| `--domain` | `my.domain` | API group suffix → `guestbook.my.domain` |
| `--repo` | `my.domain/guestbook` | Go module path in `go.mod` |

> **Note:** Neither flag needs to be a real registered domain for local development.

---

## Step 2 — Create the API

```bash
kubebuilder create api --group guestbook --version v1 --kind Guestbook
```

When prompted:
```
Create Resource [y/n] y      # creates CRD type definition
Create Controller [y/n] y    # creates the reconcile loop
```

### What gets generated

```
api/
└── v1/
    ├── guestbook_types.go          # Define your CRD schema here
    ├── groupversion_info.go        # API group/version registration
    └── zz_generated.deepcopy.go   # Auto-generated, never edit

internal/
└── controller/
    └── guestbook_controller.go    # Reconcile loop — your business logic
```

### Understanding GVK (Group Version Kind)

The three flags form a **GVK** — the unique identifier Kubernetes uses for every resource:

```yaml
apiVersion: guestbook.my.domain/v1   # group/version
kind: Guestbook                       # kind
```

This is identical to native resources:
```yaml
apiVersion: apps/v1    # group = apps, version = v1
kind: Deployment       # kind
```

---

## Step 3 — Define the CRD Schema

Edit `api/v1/guestbook_types.go`:

```go
package v1

import (
    metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// GuestbookSpec defines the DESIRED state — what you want
type GuestbookSpec struct {
    // Number of replicas for the guestbook deployment
    // +kubebuilder:validation:Minimum=1
    // +kubebuilder:validation:Maximum=10
    Replicas int32 `json:"replicas"`

    // Docker image for the guestbook app
    Image string `json:"image"`
}

// GuestbookStatus defines the OBSERVED/ACTUAL state — what is running
type GuestbookStatus struct {
    // How many pods are actually running right now
    ReadyReplicas int32 `json:"readyReplicas,omitempty"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status

// Guestbook is the Schema for the guestbooks API
type Guestbook struct {
    metav1.TypeMeta   `json:",inline"`
    metav1.ObjectMeta `json:"metadata,omitempty"`

    Spec   GuestbookSpec   `json:"spec,omitempty"`
    Status GuestbookStatus `json:"status,omitempty"`
}

// +kubebuilder:object:root=true

// GuestbookList contains a list of Guestbook
type GuestbookList struct {
    metav1.TypeMeta `json:",inline"`
    metav1.ListMeta `json:"metadata,omitempty"`
    Items           []Guestbook `json:"items"`
}

func init() {
    SchemeBuilder.Register(&Guestbook{}, &GuestbookList{})
}
```

### Spec vs Status — The Golden Rule

| Field | Purpose | Who writes it |
|---|---|---|
| `Spec` | Desired state — what YOU want | You (via kubectl) |
| `Status` | Observed state — what IS running | The operator (controller) |

---

## Step 4 — Generate CRD Manifests

```bash
make manifests
```

This reads your `// +kubebuilder:validation` marker comments and generates:
```
config/crd/bases/guestbook.my.domain_guestbooks.yaml
```

You can inspect it:
```bash
cat config/crd/bases/guestbook.my.domain_guestbooks.yaml
```

---

## Step 5 — Write the Controller

Edit `internal/controller/guestbook_controller.go` — replace the entire file:

```go
package controller

import (
    "context"

    appsv1 "k8s.io/api/apps/v1"
    corev1 "k8s.io/api/core/v1"
    "k8s.io/apimachinery/pkg/api/errors"
    metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
    "k8s.io/apimachinery/pkg/types"
    ctrl "sigs.k8s.io/controller-runtime"
    "sigs.k8s.io/controller-runtime/pkg/client"
    "sigs.k8s.io/controller-runtime/pkg/log"

    guestbookv1 "my.domain/guestbook/api/v1"
)

// GuestbookReconciler reconciles a Guestbook object
type GuestbookReconciler struct {
    client.Client
    Scheme *runtime.Scheme
}

// +kubebuilder:rbac:groups=guestbook.my.domain,resources=guestbooks,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=guestbook.my.domain,resources=guestbooks/status,verbs=get;update;patch
// +kubebuilder:rbac:groups=apps,resources=deployments,verbs=get;list;watch;create;update;patch;delete

func (r *GuestbookReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    log := log.FromContext(ctx)

    // -------------------------------------------------------
    // STEP 1: Fetch the Guestbook custom resource
    // -------------------------------------------------------
    guestbook := &guestbookv1.Guestbook{}
    if err := r.Get(ctx, req.NamespacedName, guestbook); err != nil {
        // If not found, it was deleted — nothing to do, no error
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    // -------------------------------------------------------
    // STEP 2: Define the desired Deployment
    // -------------------------------------------------------
    deployment := &appsv1.Deployment{
        ObjectMeta: metav1.ObjectMeta{
            Name:      guestbook.Name,
            Namespace: guestbook.Namespace,
        },
        Spec: appsv1.DeploymentSpec{
            Replicas: &guestbook.Spec.Replicas,
            Selector: &metav1.LabelSelector{
                MatchLabels: map[string]string{"app": guestbook.Name},
            },
            Template: corev1.PodTemplateSpec{
                ObjectMeta: metav1.ObjectMeta{
                    Labels: map[string]string{"app": guestbook.Name},
                },
                Spec: corev1.PodSpec{
                    Containers: []corev1.Container{
                        {
                            Name:  "guestbook",
                            Image: guestbook.Spec.Image,
                            Ports: []corev1.ContainerPort{
                                {ContainerPort: 80},
                            },
                        },
                    },
                },
            },
        },
    }

    // -------------------------------------------------------
    // STEP 3: Set owner reference for automatic garbage collection
    // When Guestbook is deleted → Deployment is deleted automatically
    // -------------------------------------------------------
    if err := ctrl.SetControllerReference(guestbook, deployment, r.Scheme); err != nil {
        return ctrl.Result{}, err
    }

    // -------------------------------------------------------
    // STEP 4: Create Deployment if it doesn't exist
    //         Update it if spec has changed
    // -------------------------------------------------------
    found := &appsv1.Deployment{}
    err := r.Get(ctx, types.NamespacedName{
        Name:      deployment.Name,
        Namespace: deployment.Namespace,
    }, found)

    if errors.IsNotFound(err) {
        // Deployment does not exist — create it
        log.Info("Creating Deployment", "name", deployment.Name)
        if err := r.Create(ctx, deployment); err != nil {
            log.Error(err, "Failed to create Deployment")
            return ctrl.Result{}, err
        }
    } else if err != nil {
        // Unexpected error fetching deployment
        return ctrl.Result{}, err
    } else {
        // Deployment exists — check if replicas or image changed
        if *found.Spec.Replicas != guestbook.Spec.Replicas ||
            found.Spec.Template.Spec.Containers[0].Image != guestbook.Spec.Image {
            found.Spec.Replicas = &guestbook.Spec.Replicas
            found.Spec.Template.Spec.Containers[0].Image = guestbook.Spec.Image
            log.Info("Updating Deployment", "name", found.Name)
            if err := r.Update(ctx, found); err != nil {
                log.Error(err, "Failed to update Deployment")
                return ctrl.Result{}, err
            }
        }
    }

    // -------------------------------------------------------
    // STEP 5: Update the Status subresource
    // -------------------------------------------------------
    guestbook.Status.ReadyReplicas = found.Status.ReadyReplicas
    if err := r.Status().Update(ctx, guestbook); err != nil {
        log.Error(err, "Failed to update Guestbook status")
        return ctrl.Result{}, err
    }

    return ctrl.Result{}, nil
}

// SetupWithManager registers the controller with the manager
// and tells it to watch Guestbook resources
func (r *GuestbookReconciler) SetupWithManager(mgr ctrl.Manager) error {
    return ctrl.NewControllerManagedBy(mgr).
        For(&guestbookv1.Guestbook{}).
        Owns(&appsv1.Deployment{}).  // Also watch owned Deployments
        Complete(r)
}
```

### The Reconcile Loop — How It Works

```
Event arrives (create/update/delete of Guestbook or its Deployment)
        ↓
Reconcile(ctx, req) is called
        ↓
Fetch the Guestbook resource
        ↓
Compare desired state (Spec) vs actual state
        ↓
Create / Update / Delete child resources
        ↓
Update Status
        ↓
Return — loop waits for next event
```

> **Key insight:** Reconcile is **idempotent** — running it 10 times on the same state produces the same result. It always compares desired vs actual and closes the gap.

---

## Step 6 — Install CRDs and Run

```bash
# Install CRDs into your kind cluster
make install

# Verify CRD is registered
kubectl get crds | grep guestbook
# guestbooks.guestbook.my.domain   2024-01-01T00:00:00Z

# Run the operator locally (outside cluster, uses your kubeconfig)
make run
```

Expected output:
```
INFO    Starting manager
INFO    Starting Controller    {"controller": "guestbook"}
INFO    Starting EventSource   {"controller": "guestbook", "source": "kind source: *v1.Guestbook"}
```

> The operator is now watching for Guestbook resources. Leave this terminal running.

---

## Step 7 — Deploy Your Guestbook

Edit `config/samples/guestbook_v1_guestbook.yaml`:

```yaml
apiVersion: guestbook.my.domain/v1
kind: Guestbook
metadata:
  name: guestbook-sample
  namespace: default
spec:
  replicas: 3
  image: nginx:latest
```

Apply it in a new terminal:

```bash
kubectl apply -f config/samples/guestbook_v1_guestbook.yaml
# guestbook.guestbook.my.domain/guestbook-sample created
```

---

## Step 8 — Verify Everything Works

```bash
# Check the custom resource
kubectl get guestbooks
# NAME               AGE
# guestbook-sample   9s

# Check the deployment the operator created automatically
kubectl get deployments
# NAME               READY   UP-TO-DATE   AVAILABLE   AGE
# guestbook-sample   3/3     3            3           15s

# Check the pods
kubectl get pods
# NAME                                READY   STATUS    RESTARTS   AGE
# guestbook-sample-744555cd54-9tf85   1/1     Running   0          18s
# guestbook-sample-744555cd54-fl7kp   1/1     Running   0          18s
# guestbook-sample-744555cd54-sn8nt   1/1     Running   0          18s

# Describe to see status subresource
kubectl describe guestbook guestbook-sample
```

---

## Step 9 — Scale with the Operator

### The Operator Way (correct)

```bash
# Patch the Guestbook resource — the operator reacts automatically
kubectl patch guestbook guestbook-sample --type=merge -p '{"spec":{"replicas":5}}'

# Watch pods scale up in real time
kubectl get pods -w
```

### Why NOT to use kubectl scale directly

```bash
# ❌ WRONG — bypasses the operator
kubectl scale deployment guestbook-sample --replicas=5

# Even if this works temporarily, the reconcile loop will
# revert it back to whatever is in Guestbook.Spec.Replicas
```

> **Golden Rule:** You only talk to your Custom Resource — never to the resources it manages. The CR is the single source of truth.

---

## Step 10 — Delete and Cleanup

### Delete the Guestbook Resource

```bash
kubectl delete guestbook guestbook-sample
# guestbook.guestbook.my.domain "guestbook-sample" deleted
```

### Verify Automatic Cascade Deletion

```bash
# Deployment is automatically deleted
kubectl get deployments
# No resources found in default namespace.

# Pods are automatically deleted
kubectl get pods
# No resources found in default namespace.
```

### Why Cascade Deletion Works — Owner References

When we called `ctrl.SetControllerReference(guestbook, deployment, r.Scheme)` in the controller, Kubernetes added an **ownerReference** to the Deployment:

```yaml
# kubectl get deployment guestbook-sample -o yaml
metadata:
  ownerReferences:
  - apiVersion: guestbook.my.domain/v1
    blockOwnerDeletion: true
    controller: true
    kind: Guestbook
    name: guestbook-sample
    uid: abc-123-def-456
```

Kubernetes **garbage collector** watches owner references. When the owner (Guestbook) is deleted, it automatically deletes all owned resources (Deployment → ReplicaSet → Pods).

### Delete Just a Pod (Reconcile Self-Healing)

```bash
# Manually delete a pod
kubectl delete pod guestbook-sample-744555cd54-9tf85

# The operator (via Deployment) immediately recreates it
kubectl get pods
# Notice a new pod appears — the operator healed itself
```

### Uninstall the CRD

```bash
# Remove CRD from the cluster entirely
make uninstall

# Verify
kubectl get crds | grep guestbook
# (no output — CRD is gone)
```

---

## Interview Questions & Answers

---

### Q1: What is a Kubernetes Operator?

> **Answer:**
> A Kubernetes Operator is an application-specific controller that extends the Kubernetes API to create, configure, and manage instances of complex stateful applications. It encodes human operational knowledge into software — things like how to deploy, scale, upgrade, and recover an application. It does this by defining Custom Resources (CRDs) and running a controller that continuously reconciles the desired state in the CR against the actual state in the cluster.

---

### Q2: What is the difference between a Controller and an Operator?

> **Answer:**
> Every Operator contains a Controller, but not every Controller is an Operator.
>
> A **Controller** is the generic reconcile loop pattern — it watches resources and acts on changes. Kubernetes has built-in controllers for Deployments, ReplicaSets, Jobs, etc.
>
> An **Operator** is a Controller that manages a Custom Resource (CRD) and encodes domain-specific operational logic. For example, a Postgres Operator knows not just how to run a pod, but how to handle backups, failover, version upgrades, and connection pooling — all automatically.

---

### Q3: What is GVK and why does it matter?

> **Answer:**
> GVK stands for Group, Version, Kind — the three-part unique identifier Kubernetes uses for every resource type, both native and custom.
>
> - **Group:** The API group, e.g., `apps`, `guestbook.my.domain`
> - **Version:** The API version, e.g., `v1`, `v1beta1`
> - **Kind:** The resource type, e.g., `Deployment`, `Guestbook`
>
> Together they form the `apiVersion` and `kind` fields in every YAML manifest:
> ```yaml
> apiVersion: apps/v1    # group/version
> kind: Deployment       # kind
> ```
> GVK matters because it's how the API server routes requests, how controllers register watches, and how RBAC policies are applied.

---

### Q4: What is the Reconcile loop and what properties should it have?

> **Answer:**
> The Reconcile loop is the core function of every controller. It is called whenever a watched resource changes, and its job is to compare desired state (Spec) with actual state, then take action to close the gap.
>
> It must have two critical properties:
>
> 1. **Idempotent:** Running it multiple times on the same state produces the same result — no unintended side effects.
> 2. **Level-triggered (not edge-triggered):** It doesn't react to "what changed" — it reacts to "what is the current state." This makes it resilient to missed events.
>
> If Reconcile returns an error, the controller-runtime automatically requeues the request and retries with exponential backoff.

---

### Q5: What is the difference between Spec and Status?

> **Answer:**
> - **Spec** is the desired state — what the user declares they want. It is written by the user via `kubectl apply` or `kubectl patch`.
> - **Status** is the observed state — what is actually running in the cluster right now. It is written exclusively by the controller/operator.
>
> This separation is a core Kubernetes API convention. It allows the system to clearly distinguish intent (Spec) from reality (Status), and it's why controllers can detect drift — when Status doesn't match Spec, the reconcile loop has work to do.

---

### Q6: What are Owner References and why are they important?

> **Answer:**
> Owner References are metadata fields on a Kubernetes object that link it to a parent object. When you set `ctrl.SetControllerReference(parent, child, scheme)`, Kubernetes adds an `ownerReferences` entry to the child object.
>
> This enables **automatic garbage collection** — when the parent is deleted, the Kubernetes garbage collector automatically deletes all objects that have an owner reference pointing to it.
>
> In our Guestbook example, the Deployment has an owner reference to the Guestbook CR. When we delete the Guestbook, Kubernetes automatically deletes the Deployment, which cascades to the ReplicaSet and Pods. This is how operators provide clean, automatic cleanup without requiring any explicit deletion logic in the controller.

---

### Q7: Why should you never use kubectl scale directly on operator-managed resources?

> **Answer:**
> Because the operator's reconcile loop will revert your change. The Custom Resource (CR) is the single source of truth. The operator continuously watches the CR and ensures the actual state matches `CR.Spec`. If you manually scale the Deployment to 5 replicas but the CR has `replicas: 3`, the next reconcile cycle will scale it back to 3.
>
> The correct way is to update the CR itself — `kubectl patch guestbook my-app --type=merge -p '{"spec":{"replicas":5}}'` — and let the operator react to that change.

---

### Q8: What does `make manifests` do?

> **Answer:**
> It runs `controller-gen` to scan your Go code for `// +kubebuilder:` marker comments and generates Kubernetes YAML manifests from them. Specifically it generates:
>
> - **CRD YAML** from your `_types.go` validation markers (min/max values, required fields, enums)
> - **RBAC YAML** from the `// +kubebuilder:rbac:` markers on your Reconcile function
> - **Webhook configurations** if you've defined webhooks
>
> This means your Go structs and marker comments are the single source of truth for your API schema — you never hand-write CRD YAML.

---

### Q9: What happens when the Reconcile loop returns an error?

> **Answer:**
> When Reconcile returns a non-nil error, the controller-runtime automatically requeues the request for retry. It uses **exponential backoff** — the delay between retries increases with each failure to avoid hammering the API server. The request goes back into the work queue and Reconcile is called again after the backoff period.
>
> If Reconcile returns `ctrl.Result{RequeueAfter: time.Minute}`, it requeues after a fixed duration without treating it as an error — useful for polling external systems.
>
> If it returns `ctrl.Result{}` with no error, the reconciliation is considered complete and no requeue is scheduled (until the next watch event).

---

### Q10: What is the difference between `make install` and `make run`?

> **Answer:**
> - **`make install`** registers the CRD (Custom Resource Definition) with the Kubernetes API server. After this, the cluster understands what a `Guestbook` resource is, and you can `kubectl apply` Guestbook YAML. But nothing is watching or acting on it yet.
>
> - **`make run`** starts the operator process locally (outside the cluster, using your kubeconfig). It starts the controller manager, which begins watching for Guestbook resources and running the reconcile loop when they change.
>
> You need both: `make install` teaches Kubernetes about your CRD, and `make run` starts the brain that acts on it.

---

## Quick Reference — Key Commands

```bash
# Initialize project
kubebuilder init --domain my.domain --repo my.domain/guestbook

# Create API + Controller
kubebuilder create api --group guestbook --version v1 --kind Guestbook

# Generate CRD manifests from marker comments
make manifests

# Generate DeepCopy methods
make generate

# Install CRDs into cluster
make install

# Run operator locally
make run

# Apply a sample resource
kubectl apply -f config/samples/guestbook_v1_guestbook.yaml

# Check custom resources
kubectl get guestbooks

# Scale via the operator (correct way)
kubectl patch guestbook guestbook-sample --type=merge -p '{"spec":{"replicas":5}}'

# Delete resource (cascades to Deployment + Pods)
kubectl delete guestbook guestbook-sample

# Uninstall CRDs from cluster
make uninstall
```

---

## Mental Model Summary

```
kubebuilder init          → Project scaffold
kubebuilder create api    → CRD types + Controller scaffold
make manifests            → Generate CRD YAML from Go markers
make install              → Register CRD with Kubernetes API server
make run                  → Start operator (watch + reconcile loop)
kubectl apply <CR>        → Trigger first reconcile
Reconcile()               → Create Deployment, update Status
kubectl patch <CR>        → Trigger reconcile → Update Deployment
kubectl delete <CR>       → Owner refs → cascade delete everything
```

---

*Built with Kubebuilder on Kubernetes v1.35.0 | kind 3-node cluster*
