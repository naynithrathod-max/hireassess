# Getting it on the cloud without Azure

Azure for Students checks whether your college's email domain is on Microsoft's
list. Jain University is not on it. That is a check on the *domain*, not on you,
and it does not stop you using the cloud.

Two free routes below. Neither asks for a card.

---

## Route 1 — GitHub Codespaces (recommended)

A Codespace is a Linux machine that GitHub runs in their cloud. You get a
terminal in your browser, Docker is available, and you can make the running app
reachable at a public URL.

GitHub's billing documentation states that personal accounts include **120 free
compute hours and 15 GB-months of storage per month**, and that a payment method
only matters once that quota is used up — without one, usage is simply blocked
rather than charged. Your project needs an hour or two at most.

### Steps

**1. Create a GitHub account** at `github.com`. Free, email only.

**2. Create a repository.** Click the **+** at the top right → **New
repository**. Name it `hireassess`. Leave it Public. Click **Create**.

**3. Upload the project.** On the new empty repository page, click
**uploading an existing file**. Open your `hireassess` folder in File Explorer,
select everything inside it, and drag it into the browser.

Two things to watch:
- Upload the *contents* of the folder, not the folder itself
- The `.devcontainer` folder matters. If File Explorer hides it, turn on
  **View → Show → Hidden items** first

Click **Commit changes**.

**4. Launch the Codespace.** On the repository page, click the green **Code**
button → **Codespaces** tab → **Create codespace on main**.

Wait two or three minutes. A browser-based editor opens with a terminal at the
bottom.

**5. Build and run.** In that terminal, paste the same two commands you already
know:

```
docker build -t hireassess:latest .
docker run -d --name hireassess -p 8000:8000 -v assessment-data:/data hireassess:latest
```

**6. Make the URL public.** A **Ports** tab sits next to the terminal. Port 8000
appears there. Right-click it → **Port Visibility** → **Public**.

Now click the globe icon next to the port. That opens your app at a public URL
ending in `.app.github.dev`. Open it on your phone to prove it is genuinely on
the internet.

### What to say about it in the demo

This is real IaaS. GitHub runs a Linux VM in Microsoft's cloud; your container
runs inside it; the public URL is served from their infrastructure, not your
laptop. The same image you built at home runs there unchanged — which is exactly
the portability argument.

Stop the Codespace when you are finished (**Code** → **Codespaces** → the `...`
menu → **Stop codespace**) so it stops consuming your free hours.

---

## Route 2 — Google Cloud Shell (simpler, but the URL is private)

Log in at `shell.cloud.google.com` with any Gmail account. No card, no student
verification. You get a free Linux VM with Docker already installed.

Upload your project folder with the **⋮** menu → **Upload**, then run the same
two Docker commands. Click **Web Preview** in the toolbar and change the port to
8000.

**The catch:** Google's documentation says the preview URL is restricted to your
own account over the Cloud Shell proxy, so other people cannot open it. You can
still demo it from your own screen, and it is still a genuine cloud VM, but you
cannot hand the link to your teacher.

Use this if GitHub feels like too many steps.

---

## Route 3 — reopen the Azure door in the background

Worth starting even if you use Route 1, because it costs you ten minutes and may
land before your deadline.

Microsoft support advises that when a college domain is not recognised, students
can request **manual verification** with documents. In the Azure portal, go to
**Help + support** → **New support request**, and choose the issue type for
student offer verification. Attach:

- Your student ID card
- An enrollment certificate or proof of registration
- A screenshot of the "domain not recognised" error
- Your full name exactly as your college records it

Reviews reportedly take one to seven business days. If it comes through, the
Azure steps in `SETUP.md` work as written. If it does not, you have lost nothing.

Also worth checking: the **GitHub Student Developer Pack** at
`education.github.com/pack` verifies with a student ID photo rather than an email
domain, and bundles cloud credits from several providers. Approval is not
instant, so treat it as a parallel track rather than your main plan.

---

## What this means for your marks

You are not losing anything by skipping Azure. The concepts your course cares
about are all still demonstrated:

| Concept | Where it shows up |
|---|---|
| Containers / OS-level virtualization | Docker, on your laptop and in the cloud |
| Hypervisor virtualization | The Linux VM your Codespace or Cloud Shell runs on |
| IaaS | Renting that VM instead of owning hardware |
| Public deployment model | The public `.app.github.dev` URL |
| Elasticity and cloud economics | The argument in `ARCHITECTURE.md`, unchanged |
| Portability | One image, three environments, zero code changes |

The honest line for your demo, which is worth saying out loud: *"We deployed to
GitHub Codespaces rather than Azure because our college domain is not on
Microsoft's student verification list. The architecture is provider-independent,
which is itself one of the benefits of containerising the application."*

That answer is better than a smooth one. It shows you understood the constraint
and worked around it.
