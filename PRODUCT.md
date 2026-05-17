# Veet — Product Brief

> A complete reference for AI assistants generating ads, copy, social posts,
> landing pages, or pitch decks. Paste this whole file into Claude / GPT
> with a task like "write 5 Instagram ads for Veet" and it has everything
> it needs.

---

## In one line

**Veet is voice typing for Windows that runs entirely on your computer.**
Hold Alt+Shift, speak, release — your words paste into whatever app was
just focused. No cloud, no API key, no per-second billing.

## The 10-second pitch

You type at 47 words per minute. You speak at 213. Veet bridges the gap.
Press Alt+Shift anywhere in Windows — Slack, email, your IDE, Notion,
the address bar — speak naturally, release. Your words appear, cleaned
up, in the app you were just in. The transcription model runs on your
GPU (or CPU), so your voice never leaves your machine.

## Who it's for

- **Founders, operators, and builders** who live in inbox/Slack/docs
  and want to move faster.
- **Privacy-conscious power users** who refuse cloud dictation
  (Dragon, Otter, Google Voice Typing) because their audio is sensitive.
- **People with NVIDIA GPUs** (RTX 20/30/40, GTX 16/10) who can get
  ~30× realtime transcription — basically instant.
- **Anyone who emails / messages / writes a lot on Windows** and is
  tired of typing.

## Who it's NOT for

- Mac / iOS users (Windows only, for now)
- People wanting a meeting transcription / note-taking app (use Otter)
- People who don't already have a microphone

## Features (in detail)

### Hold-to-talk hotkey
Press and hold **Alt + Shift** anywhere in Windows. Recording starts
within milliseconds. Release to transcribe and auto-paste. No
modal-switching, no clicking, no "wake word" — it's a physical button.

### Local Whisper
Uses **distil-large-v3** on GPU (~28× realtime), **distil-small.en**
on CPU (~3-5× realtime). The model downloads once on first use; after
that, the app works fully offline.

### Auto-paste into the active app
Whatever app you were in before pressing Alt+Shift gets the text. Slack,
Gmail, Notion, Word, VS Code, Photoshop, the Windows address bar — if
you can paste there, Veet can type there.

### Filler-word cleanup
"Um, hey Mark, uh, we should basically close the Henderson deal, you
know, this morning, like, et cetera" becomes "Hey Mark, we should close
the Henderson deal this morning." Removed: `um/uh/er/erm/hmm/ahh`,
`you know`, `i mean`, `et cetera`, `basically/literally/honestly`, `like`
as filler, `kind of/sort of`.

### Self-correction handling
"Build for speed and privacy, oh no no no, build for fast and privacy"
becomes "Build for fast and privacy." Veet recognizes the "no, no, no"
pattern and discards the corrected-away clause.

### Stutter dedup
"The the the meeting" → "The meeting". "Looking at the, looking at the
deal" → "Looking at the deal."

### Auto-bullets
"Hey mom, this is the grocery list butter eggs and milk" pastes as:

```
Hey mom, this is the grocery list:
• Butter
• Eggs
• Milk
```

Triggered by phrases like *grocery list*, *to-do list*, *shopping list*,
*items*, etc.

### Glass overlay pill
A 144×44 px pill appears bottom-center while recording, with a pulsing
white dot + the word **Listening**. On release it eases into **Transcribing**
with a spinner. The pill uses backdrop capture + blur + dark tint + top
inner highlight + bottom inner shadow for a real "liquid glass" look.

### Healing-frequency chimes
A soft 528 Hz pure-sine tone on press, 396 Hz on release. Hann-shaped
envelope (no clicks), 250 ms trailing silence (no driver pops). Both
chimes are saved as WAVs in `assets/` so they're user-swappable.

### Word-by-word ease-in for the demo
The website's preview animates each word fading + sliding up — matches
how voice transcription actually feels (speech → text in real chunks,
not character-by-character).

### Smart hardware detection
On first run, Veet probes for cuBLAS via `ctypes.WinDLL`. If found →
runs on GPU (float16). If not → falls back to CPU (int8) automatically.
No setup, no flags, no dialog.

### System tray app
Lives in the tray with the Veet waveform icon. Right-click for Pause /
Resume / Quit. Doesn't steal focus, doesn't appear in the taskbar.

### Auto-start on boot
The installer registers Veet in the user's startup folder by default,
so it's always ready after a reboot. (Uninstaller cleans it up.)

### Persistent audio streams
Both the InputStream (microphone) and chime playback are designed for
zero-latency response: input is always-on with a `recording` flag,
chimes play via Windows' native WinMM (no PortAudio idle issues).

### License gate (in v0.2.0+)
First launch shows a beautiful frameless modal asking for the email used
at purchase. App validates via a serverless function that queries Stripe.
14-day offline grace period. Locks on subscription cancellation.

## Benefits (what users actually get)

- **Reply to email 4× faster** — talk through inbox in minutes, not hours
- **Save 2+ hours every week** — that's 100+ hours per year
- **Document calls without typing** — speak notes, they're already formatted
- **Brainstorm at thinking speed** — your fingers can't keep up with ideas anyway
- **Type code comments / docstrings** without breaking flow
- **Reply to clients in seconds, not minutes** — close deals faster
- **Reduce RSI / typing strain** — your wrists thank you
- **Privacy that isn't a marketing claim** — your audio physically never
  leaves your computer (network blocked? Veet still works)

## Pricing

| Plan | Price | Best for |
|---|---|---|
| Monthly | $6 / mo | Try it commitment-free |
| **Yearly** | **$45 / yr (38% off)** | The recommended option |
| Lifetime | $99 once | Long-haul users, privacy maximalists |

All plans get every feature + every future update. Cancel anytime.

## Brand identity

### Voice
- **Terse.** Cut words. *"Hold to talk."* not *"Please press and hold."*
- **Direct.** Say what happens, not what could.
- **Confident.** No "please", no "kindly", no emoji (unless requested).
- **Specific.** Numbers, not adjectives. *"~28× realtime"* not *"super fast"*.

### Don't
- Don't call it "AI voice dictation" — it's **voice typing**
- Don't compare it to ChatGPT — it's not chat, it's a power tool
- Don't lead with privacy — lead with speed; privacy is the kicker

### Tagline candidates
- **Voice typing, locally.** (the canonical one)
- Hold. Talk. Done.
- Your voice. Your machine.
- Type at the speed of speech.
- Talk at 213 WPM.

## Visual identity

- **Mark**: waveform-V (8 vertical rounded bars forming a V shape)
- **Backdrop**: iOS-style rounded square, 22% corner radius
- **Highlight**: soft cyan radial glow anchored top-right of the icon
- **Surface**: `#0F1115` (near-black)
- **Glass**: rgba(22,24,32,0.45) with backdrop-blur
- **Accent**: `#67E8F9` (cyan)
- **Text**: `#F5F5F8` (off-white)
- **Text-2**: `#9AA0A6` (muted)
- **Typography**: Inter (variable, weights 400–800)

## Speed numbers (for ads)

- Keyboard average: **47 WPM**
- Speech average: **213 WPM**
- → **~4.5× faster** with voice
- Typical voice clip: 1–20 seconds
- Transcription latency on RTX 3050+: **0.3–0.7 seconds**
- Transcription latency on CPU: 1–6 seconds
- First-press latency (audio capture starts): **<5 ms** (persistent stream)
- Chime latency (audible feedback on press): **<15 ms** (WinMM)
- Hotkey detection: **<1 ms** (low-level keyboard hook)

## Tech moats / differentiation

| Veet | Cloud dictation (Dragon, Otter, Google) |
|---|---|
| Audio never leaves machine | Audio uploaded to vendor servers |
| Works offline | Requires internet |
| No per-minute billing | Per-minute or per-month with caps |
| $99 lifetime option | $15-30/month, indefinitely |
| Distil-Whisper accuracy | Variable, depends on vendor |

| Veet | Built-in Windows dictation (Win+H) |
|---|---|
| Hold-to-talk (Alt+Shift) | Modal — opens a separate input |
| Filler cleanup + smart formatting | Raw transcription |
| Distil-Whisper (state of art) | Older Microsoft model |
| Auto-paste into ANY app | Some apps don't play well |
| Visual feedback (glass pill) | Tiny floating icon |

## Common objections + responses

**"I'll just use ChatGPT voice mode"**
ChatGPT is for talking to an AI. Veet is for typing. You can talk to
ChatGPT *with* Veet — paste a prompt 5× faster.

**"I'll just use Windows dictation"**
Windows dictation opens a modal. Veet works inline — hold a key,
speak, release, done. And Veet's model is meaningfully better at
punctuation and casual speech.

**"$6/mo for voice typing? I can use Whisper on GitHub for free"**
Sure. You'll also need to: install Python, set up CUDA libs (1.2GB),
write the audio capture, write the hotkey listener, write the
clipboard handler, write the filler-cleanup, package it nicely, and
maintain it. Or pay $6/mo.

**"What about Mac?"**
On the roadmap. Windows first — that's where the audience is.

**"What about my voice being sent somewhere?"**
It isn't. The model runs on your GPU/CPU. Sniff your network traffic
and you'll see the only network call is to `veet.space/api/validate`
sending your email (for subscription verification) — never audio.

**"Will it work for accents / non-native English?"**
Distil-Whisper handles English very well across accents. For other
languages, set `VEET_LANG=multi` and it'll auto-detect.

**"What about the SmartScreen 'unknown publisher' warning?"**
We're getting an EV code-signing certificate. Until then, click
"More info" → "Run anyway". The .exe is signed locally and the
source is open at github.com/vladleonte27/veet.

## Audience moments (when they need Veet most)

- Friday afternoon, 47 unread emails, want to clear inbox before weekend
- Just hung up a client call, need to send a follow-up summary
- Brainstorming a Notion doc, fingers can't keep up with thoughts
- Drafting a long Slack reply, don't want to type 3 paragraphs
- Coding, need to write a long docstring or PR description
- iMessage / WhatsApp on desktop, replying to friends
- Filling out a long form (job application, customer survey)

## Ad copy starters

### Hook ideas (5-8 words)
- "Talk at 213 WPM."
- "Type with your voice. Privately."
- "Voice typing that doesn't go anywhere."
- "Your inbox at speech-speed."
- "Stop typing. Start talking."
- "Hold. Talk. Pasted."
- "Your fingers do 47. Your mouth does 213."

### Body angles
- **Speed**: time math — "30 emails × 2 min each = 60 min. Veet cuts that to 12."
- **Privacy**: contrast — "Otter uploads your audio. Veet doesn't."
- **Simplicity**: zero-setup — "Install. Alt+Shift. Done."
- **Universality**: every app — "Works wherever you can paste."
- **Permanence**: lifetime tier — "$99 once. Used daily for 5 years = $0.05/day."

### CTA buttons
- Install for Windows
- Try Veet
- Get Veet for $6
- Start typing faster
- Activate your voice

## Stack / architecture (technical curiosity)

- **App**: Python 3.12, packaged via PyInstaller into a 261 MB folder
- **Installer**: Inno Setup 6, 70 MB single .exe
- **Transcription**: faster-whisper 1.2 + CTranslate2 4.7 + bundled cuBLAS/cuDNN
- **UI**: tkinter + Pillow for the glass pill rendering
- **Audio**: sounddevice (PortAudio) for input, winsound (WinMM) for chimes
- **Hotkey**: `keyboard` library, low-level Win32 hook
- **Tray**: pystray
- **Distribution**: GitHub Releases (free CDN, unlimited bandwidth on public repos)
- **Website**: static HTML/CSS/JS on Vercel, custom domain veet.space
- **Payments**: Stripe Payment Links
- **License validation**: Vercel serverless function (Python) querying Stripe API

## Links

- Site: https://veet.space
- Download: https://github.com/vladleonte27/veet/releases/latest/download/Veet-Setup.exe
- Code: https://github.com/vladleonte27/veet
- Contact: vlad@vlmedia.online
- Built by: Vlad Leonte / VL Media

---

*Use this document as ground truth for any AI-assisted content
generation. If a claim isn't in here, ask before inventing it.*
