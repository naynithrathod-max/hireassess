# Architecture and the cloud justification

This is the reference for the questions you will be asked about the system.

---

## The architecture

```
                        Candidate's browser          Company's browser
                               |                            |
                               |         HTTP               |
                               v                            v
        +---------------------------------------------------------------+
        |   CLOUD VM  (Azure B1s, Ubuntu)   <-- IaaS                     |
        |   The provider's hypervisor carves this VM out of shared       |
        |   physical hardware. Other tenants share the metal; our VM     |
        |   is isolated from them.                                       |
        |                                                               |
        |   +-------------------------------------------------------+   |
        |   |  DOCKER CONTAINER   <-- OS-level virtualization        |   |
        |   |                                                       |   |
        |   |   gunicorn (2 workers)                                |   |
        |   |      |                                                |   |
        |   |   Flask application                                   |   |
        |   |      |-- /register   consent captured                 |   |
        |   |      |-- /test       timed round, answer key scoring  |   |
        |   |      |-- /written    rubric scoring engine            |   |
        |   |      |-- /scorecard  percentile vs cohort             |   |
        |   |      |-- /company    consent-filtered pool            |   |
        |   |      |-- /reviewer   human confirms rubric scores     |   |
        |   |      +-- /health     load-balancer probe              |   |
        |   +-------------------------------------------------------+   |
        |                          |                                    |
        |                  Docker volume  (/data)                       |
        |                  SQLite database                              |
        +---------------------------------------------------------------+
                                   |
                                   v
                    Azure Blob Storage   <-- cloud object storage
                    One JSON scorecard object per attempt
                    (falls back to the volume if unreachable)

        Optional:  AI scoring API  <-- FaaS-style pay-per-call
                   Pre-scores the written answer; a human confirms.
                   Absent by default; rules are used instead.
```

### Where each course concept lives

| Concept | In this project |
|---|---|
| **IaaS** | The Azure VM. We rent compute; Microsoft runs the hardware. |
| **PaaS** | Azure Blob Storage, and a managed database if added. We never patch it. |
| **FaaS / pay-per-use** | The optional AI scoring call: billed per request, nothing when idle. |
| **Hypervisor virtualization** | The VM itself, both on Azure and in VirtualBox. |
| **OS-level virtualization** | The Docker container, sharing the host kernel. |
| **Public deployment model** | Where it runs today. |
| **Hybrid deployment model** | What a real version would need: candidate PII in a private environment, public cloud for delivery. |
| **Elasticity** | Exam-day spikes versus near-zero traffic the rest of the month. |
| **Cloud economics** | Opex not capex; a cost estimate you can show. |
| **Shared responsibility** | Microsoft secures the hardware and hypervisor; we secure the app, the secrets and the consent logic. |

---

## Why cloud computing, for this platform specifically

Four facts about the product, each forcing a cloud answer.

**1. Demand is extremely spiky.** An entrance-style exam is idle for weeks, then
hundreds of candidates start within the same minute, then it is idle again.
Buying hardware for the peak means paying all year for capacity used on a handful
of days. Renting it means paying for the peak only while it lasts.

**2. There is no capital.** The blueprint's Phase 0 charges nobody. Servers are
capital expenditure before a single rupee of revenue; cloud is operating
expenditure that starts near zero and grows only with adoption.

**3. The users are spread out.** Candidates are in different colleges, hiring
partners in different cities. A public URL reaches all of them; a machine under a
desk reaches nobody.

**4. Trust is the product.** The blueprint names trust and adoption as the
biggest risk. A crash during an exam destroys it. Provider infrastructure,
snapshots and health checks are how a two-person team gets reliability it could
not build itself.

---

## Why virtualization, for this platform specifically

| Benefit | Where it shows up here |
|---|---|
| **Isolation** | Candidate data sits inside our VM, cut off from every other tenant on the same physical host. |
| **Hardware efficiency** | The provider packs many tenants onto one machine, which is why a small VM costs so little. |
| **Portability** | One image runs identically on a laptop, in VirtualBox and on Azure. This is why there is no "works on my machine" problem. |
| **Consistency of scoring** | The blueprint says inconsistent scoring collapses the value proposition. Every scorer runs the identical environment, down to the library versions. |
| **Fast recovery** | A VM snapshot restores a broken machine in seconds. |
| **Safe experimentation** | A new rubric can be tested in a throwaway container without touching the live one. |

### VM and container together

Both are in the project on purpose, and the difference is worth one slide.

| | Virtual machine | Container |
|---|---|---|
| Virtualizes | Hardware, via a hypervisor | The operating system |
| Contains | A full guest OS and kernel | Just the app and its dependencies |
| Size | Gigabytes | Hundreds of megabytes |
| Start time | Tens of seconds | Under a second |
| Isolation | Stronger | Lighter |

The VM gives strong isolation between tenants. The container gives speed and
portability within our own tenancy. Production systems use both, which is
exactly what this project does.

---

## Questions you should expect

**"Your demo has one user. Why do you need the cloud?"**
It does not, strictly. The demo proves the architecture is ready for the real
load without a rewrite. Saying this plainly is stronger than overclaiming, and
you can follow it with the two-container demo to show the path to scale.

**"Why not just use a laptop or college server?"**
No public access, one point of failure, capacity fixed at purchase, and someone
has to patch it. The cost comparison is the clincher: a server bought for a few
exam days a year sits idle for the rest.

**"What stops a company seeing a candidate who said no?"**
The consent filter is in the SQL query behind the company portal, not in the page
template. Candidates who have not consented are never loaded, so there is nothing
to leak. You can demonstrate it live by withdrawing consent and refreshing.

**"Is the AI scoring reliable?"**
It is not trusted on its own. Every rubric score is confirmed or overridden by a
human reviewer before it reaches a company, which is the blueprint's own Phase 1
position. The system defaults to a deterministic rule-based engine.

**"How would this scale to ten thousand candidates?"**
Move SQLite to a managed database, run several containers behind a load balancer,
move scorecards to object storage (already supported by one environment
variable), and add autoscaling triggered by exam schedule. None of that changes
the application code.

**"What are the security weaknesses?"**
Honest answer: passcodes instead of real authentication, no encryption at rest
beyond what the provider gives, no audit log, and a single region. For a
prototype that is acceptable; for real candidate data it is not, and the fixes
are known.

---

## Cost estimate

Fill this in from the Azure pricing calculator on the day — do not use invented
numbers, a teacher may check.

| Item | Monthly cost |
|---|---|
| B1s VM, running 24/7 | _from calculator_ |
| B1s VM, stopped except for exams | _much lower_ |
| Blob storage, a few MB | effectively zero |
| **Total during the project** | **covered by student credit** |

The comparison that makes the economics point: buying a server costs a large sum
once, whether or not anyone sits an exam that month. Renting costs a small amount
per hour and nothing while deallocated.
