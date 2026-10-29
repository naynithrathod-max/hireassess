# Setup and demo guide

Everything here costs nothing. You never need a credit card for Layer 1, and
Layer 2 runs on student credit.

You do not need to write any code. Every command below is copy-paste.

---

## What you are building

Three layers. Each one works on its own, so if a later layer fails you still
have a complete working demo.

| Layer | What runs where | Cloud concept it demonstrates | Needs |
|---|---|---|---|
| **A** | The app in a Docker container on your laptop | OS-level virtualization, containers | Docker Desktop |
| **B** | The same container inside a Linux VM on your laptop | Hypervisor virtualization, IaaS in miniature | VirtualBox, 8 GB RAM |
| **C** | The same container on a cloud VM with a public URL | Real IaaS, cloud economics, elasticity | Azure student credit |

**Build A first.** It takes about fifteen minutes and it alone is a working demo.

---

## Layer A — run it on your laptop

### A1. Install Docker Desktop

Download from `docker.com` and install it. On Windows it will ask to enable WSL 2;
accept. Restart when asked, then open Docker Desktop and wait until the whale
icon in your taskbar stops animating.

Check it worked. Open PowerShell (Windows) or Terminal (Mac) and run:

```
docker --version
```

You should see a version number. If you see "command not found", Docker Desktop
is not running yet.

### A2. Get the project onto your machine

Unzip `hireassess.zip` somewhere easy, for example `C:\hireassess` or
`~/hireassess`. Then move into that folder:

```
cd C:\hireassess
```

On Mac:

```
cd ~/hireassess
```

### A3. Build the image

```
docker build -t hireassess:latest .
```

The first run downloads the Python base image and takes two to five minutes.
Later builds take seconds. The last line should say `naming to ... hireassess:latest`.

**What just happened, for the demo:** Docker read the `Dockerfile` and produced an
*image* — a sealed, self-contained package holding Python, the libraries and the
app. The image is the unit of portability. Nothing about it depends on your laptop.

### A4. Run the container

```
docker run -d --name hireassess -p 8000:8000 -v assessment-data:/data hireassess:latest
```

Open `http://localhost:8000` in your browser. The app is live.

**What the flags mean** (worth knowing, a teacher may ask):

| Flag | Meaning |
|---|---|
| `-d` | Run in the background |
| `--name hireassess` | Give the container a name you can refer to |
| `-p 8000:8000` | Map port 8000 on your laptop to port 8000 inside the container |
| `-v assessment-data:/data` | Attach a persistent volume, so data survives the container being destroyed |

### A5. Useful commands

```
docker ps                      # what is running
docker logs -f hireassess      # watch live request logs
docker stop hireassess         # stop it
docker start hireassess        # start it again
docker rm -f hireassess        # delete the container (the volume survives)
```

If you prefer, `docker compose up -d` does the same thing using
`docker-compose.yml`, and `docker compose down` stops it.

---

## Layer B — the VirtualBox VM

This is the layer that makes *hypervisor virtualization* visible. You create a
virtual computer inside your real computer, and run the container inside it.

### B1. Install

- VirtualBox, free from `virtualbox.org`
- An Ubuntu Server ISO, free from `ubuntu.com/download/server`

### B2. Create the VM

In VirtualBox: **New** → name it `cloud-demo` → Type: Linux, Version: Ubuntu
64-bit → 2048 MB RAM or more → create a 20 GB virtual disk → **Start**, and pick
the Ubuntu ISO when it asks for a disk. Follow the Ubuntu installer, and tick
**Install OpenSSH server** when offered.

**Before you boot it**, set up port forwarding so your browser can reach the app
inside the VM: VM **Settings** → **Network** → **Advanced** → **Port Forwarding**
→ add a rule with Host Port `8080` and Guest Port `8000`.

### B3. Install Docker inside the VM and run the app

Log into the VM and run:

```
sudo apt update
sudo apt install -y docker.io
sudo usermod -aG docker $USER
```

Log out and back in. Copy the project folder into the VM (the simplest route is
a shared folder, or `git clone` if you push it to GitHub), then:

```
cd hireassess
docker build -t hireassess:latest .
docker run -d --name hireassess -p 8000:8000 -v assessment-data:/data hireassess:latest
```

From your laptop's browser, open `http://localhost:8080`.

**The point to make in the demo:** the exact same image now runs inside a virtual
machine with its own kernel, its own memory and its own disk, isolated from your
laptop. That is what a cloud provider does for every customer, at scale. Take a
screenshot of the VirtualBox window with the app visible — it is the clearest
single image of virtualization you will get.

### B4. The snapshot trick

In VirtualBox, take a **Snapshot** of the VM. Then break something deliberately
inside it, and **Restore** the snapshot. The VM returns to its exact previous
state in seconds. This is a strong thirty-second demo of why virtualization
matters for recovery.

---

## Layer C — the cloud VM

### C1. Sign up for Azure for Students

Go to `azure.microsoft.com/free/students`. Verify with your Jain University email
address. Microsoft's own FAQ says the student offer gives $100 of credit for
twelve months, and that if the credit runs out and you do not upgrade, the
subscription is **cancelled rather than billed**.

Check the signup page for whether a card is required at the time you sign up, as
these terms change. If verification fails, stop here. Layers A and B are already
a complete project.

### C2. Create the VM

In the Azure portal: **Create a resource** → **Virtual machine**.

| Setting | Choose |
|---|---|
| Image | Ubuntu Server LTS |
| Size | The smallest burstable size available, such as B1s |
| Authentication | SSH public key (the portal generates one and downloads it) |
| Inbound ports | Allow **SSH (22)** and **HTTP (80)** |

Create it, and note the **public IP address** on the overview page.

### C3. Open port 8000

Go to the VM → **Networking** → **Add inbound port rule** → Destination port
`8000`, Protocol TCP, Action Allow. Save.

### C4. Deploy

SSH in from your laptop (Azure's portal shows the exact command):

```
ssh -i path/to/key.pem azureuser@YOUR_PUBLIC_IP
```

Then, inside the VM:

```
sudo apt update
sudo apt install -y docker.io git
sudo usermod -aG docker $USER
```

Log out, SSH back in, copy the project across, then:

```
cd hireassess
docker build -t hireassess:latest .
docker run -d --restart unless-stopped --name hireassess \
  -p 8000:8000 -v assessment-data:/data hireassess:latest
```

Open `http://YOUR_PUBLIC_IP:8000` from any device, anywhere. That is your public
URL.

### C5. Money safety rules

These matter, so follow all four:

1. **Stop the VM** in the Azure portal whenever you are not testing. A stopped
   (deallocated) VM does not accrue compute charges.
2. **Set a budget alert**: Cost Management → Budgets → set one at $5 with an
   email alert. You will hear about spend long before it matters.
3. **Do not upgrade** to pay-as-you-go, however often the portal suggests it.
4. **Check your balance** in the Azure Sponsorships portal before and after the
   demo.

### C6. Optional — move scorecards to Azure Blob Storage

This adds the managed-storage (PaaS) layer. Create a Storage Account in the
portal, open **Access keys**, copy the connection string, then re-run the
container with it:

```
docker rm -f hireassess
docker run -d --restart unless-stopped --name hireassess -p 8000:8000 \
  -v assessment-data:/data \
  -e AZURE_STORAGE_CONNECTION_STRING="PASTE_IT_HERE" \
  hireassess:latest
```

Visit `/admin/info`. The storage backend now reads `azure-blob`, and completed
scorecards appear as objects in your storage account. **Nothing in the
application code changed** — only an environment variable. That is the sentence
to say out loud during the demo.

Storage accounts have a small free allowance and a few scorecard JSON files are
a few kilobytes, so the cost is effectively zero. If the connection ever fails,
the app writes locally instead rather than losing a scorecard.

---

## The demo script

Eight minutes, in this order.

**1. The problem (30 seconds).**
"A final-year student sits five separate company screening tests. We replace
that with one standardized assessment whose score report goes to partner
companies."

**2. Candidate journey (3 minutes).**
Register, tick consent, take the timed round. **Switch browser tabs once on
purpose** — the counter in the timer bar increments. Submit, write a short
answer, submit again. The scorecard appears with the percentile, the rubric
breakdown and the integrity note about your tab switch.

**3. The consent mechanism (1 minute).**
Open the company portal in a second tab (`partner2026`). Point out your own name
in the list. Go back to the scorecard, click **Withdraw consent**, refresh the
company portal. Your row is gone. Say: *"That filter runs at the database query,
so the portal never receives the data in the first place."*

**4. The human reviewer (1 minute).**
Open `/reviewer` (`reviewer2026`). Show the written answer beside its rubric
score. Override a score and save, then show that the overall score recalculates.
This is the "AI-assisted, human-reviewed" model — the human is not decorative.

**5. The infrastructure (2 minutes).** This is the part being graded.
- Show `/admin/info`: the hostname serving the request, the storage backend, the
  configuration flags.
- Show the VirtualBox window with the VM running: hypervisor virtualization.
- Show `docker ps` and `docker logs`: the container.
- Show the public Azure URL on your phone: it is genuinely on the internet.
- Say the elasticity line: *"Exam traffic is spiky. We rent capacity for exam day
  and release it afterwards instead of buying servers that sit idle."*

**6. Honest limits (30 seconds).**
*"This demo has one user, so it does not strictly need the cloud. The real
platform does, and this architecture is ready for it without a rewrite."*
Teachers reward this far more than overclaiming.

### The scaling demo, if you want one more minute

Run a second container from the same image:

```
docker run -d --name hireassess-2 -p 8001:8000 -v assessment-data:/data hireassess:latest
```

Open `localhost:8000/admin/info` and `localhost:8001/admin/info` side by side.
Different hostnames, same image, same data volume. That is horizontal scaling in
one screen.

---

## Backup plan

Have all three ready on demo day:

1. The Azure public URL.
2. The container running locally on your laptop (`docker start hireassess`).
3. A screen recording of the full flow, made the night before. Use Windows Game
   Bar (`Win + G`) or Mac `Cmd + Shift + 5`.

If the venue has no internet, number 2 still works. If Docker misbehaves, number
3 still works.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `docker: command not found` | Docker Desktop is not running. Open it and wait for the whale icon to settle. |
| `port is already allocated` | Something else uses 8000. Use `-p 8080:8000` and open `localhost:8080`. |
| Page will not load on Azure | The port rule is missing. VM → Networking → add inbound rule for 8000. |
| Container exits immediately | `docker logs hireassess` shows why. |
| Timer does not count down | JavaScript is blocked. Try a different browser. |
| Scores look wrong | `docker rm -f hireassess` then `docker volume rm assessment-data` resets everything, including the synthetic cohort. |

---

## Optional — switch on AI scoring

The app scores written answers with a rule-based rubric engine by default. No
key, no network, no cost, and the demo never depends on an external service.

If you get a free API key, pass it in and the app pre-scores with the model
instead, marks the attempt as pending human review, and still falls back to the
rules if the call fails:

```
docker run -d --name hireassess -p 8000:8000 -v assessment-data:/data \
  -e GEMINI_API_KEY="your-key" hireassess:latest
```

Free API tiers change often, so treat this as a bonus. The project is complete
without it, and the reviewer screen tells the same story either way.
