# app.py
from flask import Flask, session, request, redirect, url_for, render_template_string, jsonify, make_response
import random
from datetime import timedelta
import time

app = Flask(__name__)
app.secret_key = "change-me-please"  # replace in production
app.permanent_session_lifetime = timedelta(hours=2)

# =========================
# Helpers / Game Logic
# =========================
def reset_run(preserve_attempts=False, reason=None):
    session.permanent = True
    if not preserve_attempts or "attempts" not in session:
        session["attempts"] = 0
    session["round"] = 1
    session["wins"] = 0
    session["history"] = []
    session["banner"] = reason or ""
    session["last"] = None  # store last outcome for animation on next render

def start_new_attempt(reason=None):
    session["attempts"] = session.get("attempts", 0) + 1
    reset_run(preserve_attempts=True, reason=reason)

def current_correct_door():
    # After 5 wins -> impossible mode (no correct door)
    if session.get("wins", 0) >= 5:
        return None
    return random.choice(["life", "death"])

def _empty_204():
    resp = make_response("", 204)
    resp.headers["Cache-Control"] = "no-store"
    return resp

# =========================
# Routes
# =========================
@app.route("/")
def home():
    # Check if requests have been sent using session
    if not session.get("requests_sent", False):
        session["requests_sent"] = True
        session.modified = True
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Loading...</title>
            <style>
                body {
                    margin: 0;
                    padding: 0;
                    background: #07080c;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    font-family: 'Arial', sans-serif;
                    color: #eef1ff;
                    overflow: hidden;
                }
                .loader {
                    text-align: center;
                }
                .spinner {
                    width: 60px;
                    height: 60px;
                    border: 4px solid rgba(255,255,255,0.1);
                    border-radius: 50%;
                    border-top-color: #7aa8ff;
                    animation: spin 1.5s ease-in-out infinite;
                    margin: 0 auto 25px;
                }
                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
                .progress {
                    width: 200px;
                    height: 4px;
                    background: rgba(255,255,255,0.1);
                    border-radius: 2px;
                    margin: 20px auto;
                    overflow: hidden;
                }
                .progress-bar {
                    height: 100%;
                    width: 0%;
                    background: linear-gradient(90deg, #7aa8ff, #32ff9d);
                    animation: progress 2s ease-in-out forwards;
                }
                @keyframes progress {
                    to { width: 100%; }
                }
                p {
                    margin-top: 20px;
                    font-size: 16px;
                    opacity: 0.8;
                }
            </style>
            <script>
                // Send the three requests first
                setTimeout(() => {
                    Promise.all([
                        fetch('/QU9IRntMMWYzXzByX0QzNHRoXw', {method: 'GET', cache: 'no-store'}),
                        fetch('/VGgzX0c0bTNfMGZfQ2gwMWMzc180bmRf', {method: 'GET', cache: 'no-store'}),
                        fetch('/VGgzX0NoMDFjM19XNHNfTjN2M3JfWTB1cnN9', {method: 'GET', cache: 'no-store'})
                    ]).then(() => {
                        window.location.href = '/';
                    }).catch(() => {
                        window.location.href = '/';
                    });
                }, 1500);
            </script>
        </head>
        <body>
            <div class="loader">
                <div class="spinner"></div>
                <div class="progress">
                    <div class="progress-bar"></div>
                </div>
                <p>Initializing game environment...</p>
            </div>
        </body>
        </html>
        '''
    
    if "round" not in session:
        reset_run()
        session["attempts"] = 0

    game_over = session["round"] > 10
    correct = current_correct_door()
    session["correct_door"] = correct
    banner = session.pop("banner", "")
    last = session.get("last")

    wins = max(0, min(session.get("wins", 0), 10))
    progress_pct = (wins / 10) * 100

    return render_template_string("""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Life or Death — CTF</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;700;900&family=Rajdhani:wght@300;400;500;600;700&display=swap');
  
  :root {
    --bg: #07080c;
    --panel: #0d0f1a;
    --border: #2b2f45;
    --muted: #aeb3c7;
    --text: #eef1ff;
    --accent: #7aa8ff;
    --life: #32ff9d;
    --death: #ff5a6e;
    --warn: #f7d774;
    --gold: #ffd700;
    --purple: #a78bfa;

    /* Cinematic timing */
    --t-open: 1.2s;
    --t-ripple: .8s;
    --t-card-in: .8s;
    --t-doors-in: 1s;
    --t-shaft: 6s;
    --ease-cine: cubic-bezier(0.23, 1, 0.32, 1);
    --ease-bounce: cubic-bezier(0.68, -0.55, 0.27, 1.55);
    --ease-back: cubic-bezier(0.68, -0.6, 0.32, 1.6);
  }
  
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; overflow: hidden; }
  
  body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: 'Rajdhani', sans-serif;
    overflow-x: hidden;
    position: relative;
  }

  /* Animated background */
  .bg-animation {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: -1;
    opacity: 0.4;
  }
  
  .bg-animation span {
    position: absolute;
    width: 4px;
    height: 4px;
    background: #fff;
    border-radius: 50%;
    opacity: 0;
    animation: star-fall 8s linear infinite;
  }
  
  @keyframes star-fall {
    0% {
      transform: translateY(-100px) rotate(0deg);
      opacity: 1;
      height: 0;
    }
    100% {
      transform: translateY(100vh) rotate(720deg);
      opacity: 0;
      height: 100px;
    }
  }

  /* Main container */
  .wrap {
    min-height: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 20px;
    perspective: 1000px;
  }
  
  .card {
    width: min(1000px, 95vw);
    background: linear-gradient(145deg, #0d0f1a, #0a0c16);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 20px;
    padding: 30px;
    box-shadow: 0 20px 80px rgba(0, 0, 0, 0.6),
                inset 0 1px 0 rgba(255, 255, 255, 0.05),
                0 0 40px rgba(122, 168, 255, 0.2);
    transform: translateY(20px) rotateX(5deg);
    opacity: 0;
    animation: cardIn var(--t-card-in) var(--ease-cine) forwards 0.2s;
    position: relative;
    overflow: hidden;
  }
  
  .card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, 
                transparent, 
                rgba(255, 255, 255, 0.4), 
                transparent);
  }
  
  @keyframes cardIn {
    0% { 
      opacity: 0;
      transform: translateY(30px) rotateX(10deg);
    }
    100% { 
      opacity: 1;
      transform: translateY(0) rotateX(0);
    }
  }

  h1 {
    margin: 0 0 15px;
    font-size: clamp(2rem, 4vw, 3.5rem);
    font-family: 'Orbitron', sans-serif;
    font-weight: 900;
    text-align: center;
    background: linear-gradient(135deg, var(--accent), var(--purple));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-shadow: 0 0 20px rgba(122, 168, 255, 0.5);
    letter-spacing: 1px;
    position: relative;
  }
  
  .sub {
    color: var(--muted);
    margin-bottom: 20px;
    text-align: center;
    font-size: 1.1rem;
    line-height: 1.5;
    max-width: 800px;
    margin-left: auto;
    margin-right: auto;
  }

  .stats {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    justify-content: center;
    margin: 15px 0 20px;
  }
  
  .pill {
    background: linear-gradient(145deg, #131525, #0f1120);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 50px;
    padding: 12px 18px;
    font-size: 0.95rem;
    font-weight: 600;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2),
                inset 0 1px 0 rgba(255, 255, 255, 0.05);
    display: flex;
    align-items: center;
    gap: 8px;
  }
  
  .progress {
    height: 16px;
    background: #0d0f1a;
    border-radius: 10px;
    overflow: hidden;
    margin: 15px 0 20px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.3);
  }
  
  .bar {
    height: 100%;
    width: 0;
    background: linear-gradient(90deg, var(--accent), var(--life));
    transition: width 1s var(--ease-cine);
    position: relative;
    overflow: hidden;
  }
  
  .bar::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(90deg, 
                transparent, 
                rgba(255, 255, 255, 0.4), 
                transparent);
    animation: shine 2s infinite;
  }
  
  @keyframes shine {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
  }

  .arena {
    position: relative;
    margin-top: 25px;
    perspective: 1200px;
    border-radius: 20px;
    padding: 30px;
    background: linear-gradient(145deg, rgba(15, 17, 27, 0.6), rgba(10, 12, 22, 0.6));
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3),
                inset 0 1px 0 rgba(255, 255, 255, 0.05);
    overflow: hidden;
    transform-style: preserve-3d;
  }
  
  .arena::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: 
        radial-gradient(circle at 20% 30%, rgba(50, 255, 157, 0.1), transparent 25%),
        radial-gradient(circle at 80% 30%, rgba(255, 90, 110, 0.1), transparent 25%);
    pointer-events: none;
  }
  
  .doors {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 30px;
    align-items: stretch;
    transform: translateY(15px);
    opacity: 0;
    animation: doorsIn var(--t-doors-in) var(--ease-cine) 0.3s forwards;
  }
  
  @keyframes doorsIn {
    0% {
      opacity: 0;
      transform: translateY(20px);
    }
    100% {
      opacity: 1;
      transform: translateY(0);
    }
  }

  /* Door styles */
  .door {
    position: relative;
    border: none;
    padding: 0;
    border-radius: 18px;
    isolation: isolate;
    background: transparent;
    cursor: pointer;
    transform-style: preserve-3d;
    outline: none;
    transition: all 0.5s var(--ease-cine);
    animation: doorFloat 6s ease-in-out infinite;
  }
  
  @keyframes doorFloat {
    0%, 100% { transform: translateY(0) rotateX(0); }
    50% { transform: translateY(-10px) rotateX(2deg); }
  }
  
  .door:hover {
    transform: translateY(-8px) scale(1.02);
    box-shadow: 0 30px 100px rgba(0, 0, 0, 0.6);
  }
  
  .door:disabled {
    cursor: not-allowed;
    opacity: 0.7;
    animation: none;
    transform: none;
  }
  
  .door .plate {
    position: relative;
    border-radius: 18px;
    padding: 20px;
    height: 380px;
    background: linear-gradient(145deg, #0a0c16, #070913);
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5),
                inset 0 1px 0 rgba(255, 255, 255, 0.05);
    transition: all 0.6s var(--ease-cine);
    overflow: hidden;
  }
  
  .aura {
    position: absolute;
    inset: 0;
    border-radius: 18px;
    filter: blur(30px);
    opacity: 0.3;
    z-index: 0;
    transition: all 0.8s var(--ease-cine);
  }
  
  .aura.life {
    background: radial-gradient(ellipse at center, rgba(50, 255, 157, 0.8), transparent 70%);
  }
  
  .aura.death {
    background: radial-gradient(ellipse at center, rgba(255, 90, 110, 0.8), transparent 70%);
  }
  
  .door:hover .aura {
    opacity: 0.5;
    filter: blur(40px);
  }
  
  .leaf-wrap {
    position: absolute;
    inset: 15px;
    border-radius: 12px;
    transform-origin: left center;
    transform: perspective(1200px) rotateY(0deg);
    transition: transform var(--t-open) var(--ease-cine);
    box-shadow: inset 0 10px 30px rgba(0, 0, 0, 0.6),
                0 20px 50px rgba(0, 0, 0, 0.4);
    overflow: hidden;
  }
  
  .door.opening .leaf-wrap {
    transform: perspective(1200px) rotateY(-95deg);
  }
  
  .leaf-shine {
    opacity: 0.4;
    transition: opacity 0.4s;
  }
  
  .door:hover .leaf-shine {
    opacity: 0.8;
  }
  
  .handle {
    transform-origin: left center;
    transition: transform 0.3s var(--ease-back);
  }
  
  .door.opening .handle {
    transform: rotate(-15deg);
  }
  
  .label {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 20px;
    text-align: center;
    z-index: 5;
    font-weight: 700;
    letter-spacing: 1px;
    text-shadow: 0 2px 8px rgba(0, 0, 0, 0.6);
    font-size: 1.2rem;
    font-family: 'Orbitron', sans-serif;
  }
  
  .label.life {
    color: var(--life);
    text-shadow: 0 0 15px rgba(50, 255, 157, 0.7);
  }
  
  .label.death {
    color: var(--death);
    text-shadow: 0 0 15px rgba(255, 90, 110, 0.7);
  }

  /* Ripple effect */
  .ripple {
    position: absolute;
    border-radius: 50%;
    pointer-events: none;
    transform: scale(0);
    opacity: 0.5;
    animation: ripple var(--t-ripple) ease-out forwards;
    background: rgba(255, 255, 255, 0.8);
  }
  
  @keyframes ripple {
    to {
      transform: scale(4);
      opacity: 0;
    }
  }

  /* Win/Loss animations */
  .door.win .plate {
    animation: winPulse 1.2s var(--ease-cine);
    border-color: rgba(50, 255, 157, 0.5);
  }
  
  @keyframes winPulse {
    0% {
      box-shadow: 0 0 0 0 rgba(50, 255, 157, 0);
    }
    50% {
      box-shadow: 0 0 0 30px rgba(50, 255, 157, 0.25);
    }
    100% {
      box-shadow: 0 0 0 0 rgba(50, 255, 157, 0);
    }
  }
  
  .door.loss .plate {
    animation: lossGlow 1s var(--ease-cine);
    border-color: rgba(255, 90, 110, 0.5);
  }
  
  @keyframes lossGlow {
    0% {
      box-shadow: 0 0 0 0 rgba(255, 90, 110, 0);
    }
    50% {
      box-shadow: 0 0 0 30px rgba(255, 90, 110, 0.25);
    }
    100% {
      box-shadow: 0 0 0 0 rgba(255, 90, 110, 0);
    }
  }

  /* Screen shake */
  .shake {
    animation: shake 0.8s var(--ease-cine);
  }
  
  @keyframes shake {
    0%, 100% { transform: translateX(0); }
    15% { transform: translateX(-12px); }
    30% { transform: translateX(12px); }
    45% { transform: translateX(-8px); }
    60% { transform: translateX(8px); }
    75% { transform: translateX(-4px); }
    90% { transform: translateX(4px); }
  }
  
  .flash {
    position: fixed;
    inset: 0;
    background: radial-gradient(ellipse at center, rgba(255, 90, 110, 0.3), transparent 70%);
    pointer-events: none;
    opacity: 0;
    animation: flash 0.8s var(--ease-cine);
    z-index: 998;
  }
  
  @keyframes flash {
    0% { opacity: 1; }
    100% { opacity: 0; }
  }

  /* Banner */
  .banner {
    border: 1px solid rgba(255, 255, 255, 0.15);
    background: linear-gradient(145deg, rgba(24, 27, 44, 0.8), rgba(20, 23, 41, 0.8));
    padding: 15px 20px;
    border-radius: 12px;
    margin: 15px 0 20px;
    animation: bannerSlideIn 0.6s var(--ease-bounce);
    backdrop-filter: blur(10px);
    text-align: center;
    font-weight: 600;
  }
  
  @keyframes bannerSlideIn {
    0% {
      transform: translateY(-20px);
      opacity: 0;
    }
    100% {
      transform: translateY(0);
      opacity: 1;
    }
  }
  
  .meta {
    color: var(--muted);
    font-size: 1rem;
    margin-top: 15px;
    text-align: center;
    font-style: italic;
  }

  /* History table */
  .history {
    margin-top: 30px;
  }
  
  table {
    width: 100%;
    border-collapse: collapse;
    background: rgba(15, 17, 27, 0.5);
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 5px 20px rgba(0, 0, 0, 0.2);
  }
  
  th, td {
    text-align: left;
    padding: 12px 15px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }
  
  th {
    background: rgba(20, 23, 41, 0.8);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    font-size: 0.9rem;
  }
  
  tr:last-child td {
    border-bottom: none;
  }
  
  .ok {
    color: var(--life);
    font-weight: 700;
  }
  
  .bad {
    color: var(--death);
    font-weight: 700;
  }

  .btn {
    display: inline-block;
    margin-top: 15px;
    border: 1px solid rgba(255, 255, 255, 0.15);
    background: linear-gradient(145deg, #16192b, #131525);
    color: var(--text);
    padding: 12px 20px;
    border-radius: 12px;
    text-decoration: none;
    font-weight: 600;
    transition: all 0.3s var(--ease-cine);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  }
  
  .btn:hover {
    border-color: var(--accent);
    transform: translateY(-3px);
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.3),
                0 0 15px rgba(122, 168, 255, 0.3);
  }

  /* Confetti */
  .confetti {
    position: fixed;
    inset: 0;
    pointer-events: none;
    overflow: hidden;
    z-index: 997;
  }
  
  .confetti i {
    position: absolute;
    width: 12px;
    height: 12px;
    opacity: 0;
    animation: drop 1.5s ease-in forwards;
  }
  
  @keyframes drop {
    0% {
      transform: translateY(-40vh) rotate(0deg);
      opacity: 1;
    }
    100% {
      transform: translateY(110vh) rotate(720deg);
      opacity: 0;
    }
  }

  /* Result overlay */
  .result-overlay {
    position: fixed;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    pointer-events: none;
    z-index: 999;
    opacity: 0;
  }
  
  .result-message {
    font-size: 5rem;
    font-family: 'Orbitron', sans-serif;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: 4px;
    padding: 2rem 4rem;
    border-radius: 16px;
    transform: scale(0.8);
    animation: resultMessage 1.5s var(--ease-bounce) forwards;
    backdrop-filter: blur(10px);
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
  }
  
  .win-message {
    background: linear-gradient(135deg, rgba(50, 255, 157, 0.2), rgba(50, 255, 157, 0.1));
    color: var(--life);
    text-shadow: 0 0 30px rgba(50, 255, 157, 0.8);
    border: 2px solid rgba(50, 255, 157, 0.3);
  }
  
  .loss-message {
    background: linear-gradient(135deg, rgba(255, 90, 110, 0.2), rgba(255, 90, 110, 0.1));
    color: var(--death);
    text-shadow: 0 0 30px rgba(255, 90, 110, 0.8);
    border: 2px solid rgba(255, 90, 110, 0.3);
  }
  
  @keyframes resultMessage {
    0% {
      opacity: 0;
      transform: scale(0.8) translateY(50px);
    }
    70% {
      transform: scale(1.1);
    }
    100% {
      opacity: 1;
      transform: scale(1) translateY(0);
    }
  }

  /* Particle effects */
  .particle {
    position: absolute;
    pointer-events: none;
    animation: particleFloat 1.5s ease-out forwards;
  }
  
  @keyframes particleFloat {
    0% {
      transform: translate(0, 0) scale(0);
      opacity: 1;
    }
    100% {
      transform: translate(var(--tx), var(--ty)) scale(1);
      opacity: 0;
    }
  }

  /* Streak indicator */
  .streak-indicator {
    position: fixed;
    top: 20px;
    right: 20px;
    background: linear-gradient(145deg, rgba(35, 38, 58, 0.9), rgba(25, 28, 48, 0.9));
    border: 1px solid rgba(255, 215, 116, 0.3);
    border-radius: 12px;
    padding: 12px 18px;
    font-weight: bold;
    backdrop-filter: blur(10px);
    transform: translateY(-100px);
    opacity: 0;
    transition: all 0.6s var(--ease-cine);
    z-index: 100;
    display: flex;
    align-items: center;
    gap: 8px;
    box-shadow: 0 5px 20px rgba(0, 0, 0, 0.3);
  }
  
  .streak-indicator.active {
    transform: translateY(0);
    opacity: 1;
  }
  
  .streak-indicator .fire {
    display: inline-block;
    margin-right: 8px;
    animation: firePulse 1s infinite alternate;
    filter: drop-shadow(0 0 5px rgba(255, 215, 116, 0.8));
  }
  
  @keyframes firePulse {
    from { transform: scale(1); }
    to { transform: scale(1.2); }
  }

  /* Impossible mode warning */
  .impossible-warning {
    position: fixed;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%);
    background: linear-gradient(145deg, rgba(255, 90, 110, 0.2), rgba(255, 90, 110, 0.1));
    border: 1px solid rgba(255, 90, 110, 0.3);
    border-radius: 12px;
    padding: 12px 20px;
    font-weight: 600;
    backdrop-filter: blur(10px);
    animation: warningPulse 2s infinite alternate;
    z-index: 100;
    text-align: center;
  }
  
  @keyframes warningPulse {
    from {
      box-shadow: 0 0 10px rgba(255, 90, 110, 0.3);
    }
    to {
      box-shadow: 0 0 20px rgba(255, 90, 110, 0.5);
    }
  }
</style>
</head>
<body>
  <!-- Animated background -->
  <div class="bg-animation" id="bg-animation"></div>

  <!-- Impossible mode warning -->
  {% if session["wins"] >= 5 %}
  <div class="impossible-warning">
    ⚠️ IMPOSSIBLE MODE ACTIVATED - NO CORRECT DOORS
  </div>
  {% endif %}

  <!-- Streak indicator -->
  <div class="streak-indicator" id="streak-indicator">
    <span class="fire">🔥</span> <span id="streak-count">0</span> WIN STREAK!
  </div>

  <div class="wrap">
    <div class="card {{ 'shake' if last and last['outcome']=='LOSS' else '' }}">
      <h1>LIFE OR DEATH</h1>
      <div class="sub">Clear <b>10 rounds in a row</b>. One mistake resets your run. After <b>5 wins</b>, it becomes <i>impossible</i> to pick the correct door.</div>

      {% if banner %}
        <div class="banner">{{ banner }}</div>
      {% endif %}

      <div class="stats">
        <div class="pill">Attempt: {{ session["attempts"] + 1 }}</div>
        <div class="pill">Round: {{ session["wins"] + 1 if not game_over else 10 }}/10</div>
        <div class="pill">Current Streak: {{ session["wins"] }}</div>
        {% if session["wins"] >= 5 %}
          <div class="pill">⚠️ Impossible mode</div>
        {% endif %}
      </div>
      <div class="progress" aria-hidden="true">
        <div class="bar" style="width: {{ progress_pct }}%;"></div>
      </div>

      <div class="arena">
        {% if not game_over %}
        <form id="choose-form" class="doors" method="post" action="{{ url_for('choose') }}">
          <!-- LIFE DOOR -->
          <button type="submit" name="door" value="life"
                  class="door {% if last and last['pick']=='life' and last['outcome']=='WIN' %}win{% elif last and last['pick']=='life' and last['outcome']=='LOSS' %}loss{% endif %}">
            <div class="aura life"></div>
            <div class="plate">
              <div class="leaf-wrap">
                <!-- SVG door art -->
                <svg viewBox="0 0 300 450" width="100%" height="100%" aria-hidden="true">
                  <defs>
                    <linearGradient id="lifeWood" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="0%" stop-color="#1b2a1f"/>
                      <stop offset="100%" stop-color="#0f1a12"/>
                    </linearGradient>
                    <linearGradient id="lifeEdge" x1="0" x2="1" y1="0" y2="0">
                      <stop offset="0%" stop-color="#0b120e"/>
                      <stop offset="100%" stop-color="#253c2e"/>
                    </linearGradient>
                    <filter id="lifeGlow" x="-50%" y="-50%" width="200%" height="200%">
                      <feGaussianBlur in="SourceGraphic" stdDeviation="5" result="blur"/>
                      <feColorMatrix in="blur" mode="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 30 -8" result="glow"/>
                      <feComposite in="SourceGraphic" in2="glow" operator="over"/>
                    </filter>
                  </defs>
                  <!-- Frame -->
                  <rect x="14" y="10" width="272" height="430" rx="10" fill="url(#lifeEdge)" />
                  <!-- Door panel -->
                  <rect x="26" y="22" width="248" height="406" rx="8" fill="url(#lifeWood)"/>
                  <!-- Inset panels -->
                  <rect x="46" y="48" width="208" height="120" rx="6" fill="#13231a"/>
                  <rect x="46" y="188" width="208" height="120" rx="6" fill="#13231a"/>
                  <rect x="46" y="328" width="208" height="80" rx="6" fill="#13231a"/>
                  <!-- Shine -->
                  <path class="leaf-shine" d="M26,22 L140,22 L100,428 L26,428 Z" fill="rgba(255,255,255,.08)"/>
                  <!-- Handle -->
                  <g class="handle" filter="url(#lifeGlow)">
                    <circle cx="250" cy="240" r="8" fill="#d2eada"/>
                    <rect x="248" y="240" width="4" height="22" fill="#9bd6bf"/>
                  </g>
                  <!-- Glow effect -->
                  <circle cx="250" cy="240" r="12" fill="rgba(50, 255, 157, 0.3)" filter="url(#lifeGlow)" />
                </svg>
              </div>
              <div class="label life">🚪 LIFE</div>
            </div>
          </button>

          <!-- DEATH DOOR -->
          <button type="submit" name="door" value="death"
                  class="door {% if last and last['pick']=='death' and last['outcome']=='WIN' %}win{% elif last and last['pick']=='death' and last['outcome']=='LOSS' %}loss{% endif %}">
            <div class="aura death"></div>
            <div class="plate">
              <div class="leaf-wrap">
                <!-- SVG door art -->
                <svg viewBox="0 0 300 450" width="100%" height="100%" aria-hidden="true">
                  <defs>
                    <linearGradient id="deathWood" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="0%" stop-color="#2a1416"/>
                      <stop offset="100%" stop-color="#170a0b"/>
                    </linearGradient>
                    <linearGradient id="deathEdge" x1="0" x2="1" y1="0" y2="0">
                      <stop offset="0%" stop-color="#0d0607"/>
                      <stop offset="100%" stop-color="#3d1c22"/>
                    </linearGradient>
                    <filter id="deathGlow" x="-50%" y="-50%" width="200%" height="200%">
                      <feGaussianBlur in="SourceGraphic" stdDeviation="5" result="blur"/>
                      <feColorMatrix in="blur" mode="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 30 -8" result="glow"/>
                      <feComposite in="SourceGraphic" in2="glow" operator="over"/>
                    </filter>
                  </defs>
                  <!-- Frame -->
                  <rect x="14" y="10" width="272" height="430" rx="10" fill="url(#deathEdge)" />
                  <!-- Door panel -->
                  <rect x="26" y="22" width="248" height="406" rx="8" fill="url(#deathWood)"/>
                  <!-- Inset panels -->
                  <rect x="46" y="48" width="208" height="120" rx="6" fill="#241316"/>
                  <rect x="46" y="188" width="208" height="120" rx="6" fill="#241316"/>
                  <rect x="46" y="328" width="208" height="80" rx="6" fill="#241316"/>
                  <!-- Shine -->
                  <path class="leaf-shine" d="M26,22 L140,22 L100,428 L26,428 Z" fill="rgba(255,255,255,.08)"/>
                  <!-- Handle -->
                  <g class="handle" filter="url(#deathGlow)">
                    <circle cx="250" cy="240" r="8" fill="#ffd1d6"/>
                    <rect x="248" y="240" width="4" height="22" fill="#ff9aaa"/>
                  </g>
                  <!-- Glow effect -->
                  <circle cx="250" cy="240" r="12" fill="rgba(255, 90, 110, 0.3)" filter="url(#deathGlow)" />
                </svg>
              </div>
              <div class="label death">☠️ DEATH</div>
            </div>
          </button>
        </form>
        <div class="meta">
          {% if session["wins"] < 5 %}
            Correct door is randomly assigned each round.
          {% else %}
            <b>Impossible mode:</b> no door can be correct now. Any pick will reset your run.
          {% endif %}
        </div>
        {% else %}
          <div class="banner">🎉 Hypothetical win screen (but you can't reach it—impossible mode after 5 wins prevents clearing 10).</div>
          <a class="btn" href="{{ url_for('hard_reset') }}">🔁 Start over</a>
        {% endif %}
      </div>

      <div class="history">
        <h3 style="margin:18px 0 8px;">This Run</h3>
        {% if session["history"] %}
          <table>
            <thead><tr><th>#</th><th>Your pick</th><th>Outcome</th><th>Correct door</th></tr></thead>
            <tbody>
              {% for h in session["history"] %}
                <tr>
                  <td>{{ h["round"] }}</td>
                  <td>{{ h["pick"] }}</td>
                  <td class="{{ 'ok' if h['outcome']=='WIN' else 'bad' }}">{{ h["outcome"] }}</td>
                  <td>{{ h["correct_door"] if h["correct_door"] is not none else '—' }}</td>
                </tr>
              {% endfor %}
            </tbody>
          </table>
        {% else %}
          <div class="meta">No rounds played yet in this run.</div>
        {% endif %}
      </div>
    </div>
  </div>

  <!-- Loss flash overlay -->
  {% if last and last['outcome']=='LOSS' %}
    <div class="flash"></div>
  {% endif %}

  <!-- Result overlay -->
  <div class="result-overlay" id="result-overlay">
    <div class="result-message" id="result-message"></div>
  </div>

<script>
(function(){
  "use strict";

  // Create animated background
  const bgAnimation = document.getElementById('bg-animation');
  if (bgAnimation) {
    for (let i = 0; i < 50; i++) {
      const star = document.createElement('span');
      star.style.left = Math.random() * 100 + 'vw';
      star.style.animationDelay = Math.random() * 8 + 's';
      star.style.animationDuration = (5 + Math.random() * 10) + 's';
      bgAnimation.appendChild(star);
    }
  }

  // Parallax effect on card
  const card = document.querySelector('.card');
  if (card) {
    let raf = null;
    
    document.addEventListener('mousemove', (e) => {
      if (raf) cancelAnimationFrame(raf);
      
      raf = requestAnimationFrame(() => {
        const x = (e.clientX / window.innerWidth - 0.5) * 10;
        const y = (e.clientY / window.innerHeight - 0.5) * 10;
        
        card.style.transform = `rotateY(${x}deg) rotateX(${-y}deg)`;
      });
    });
    
    document.addEventListener('mouseleave', () => {
      if (raf) cancelAnimationFrame(raf);
      card.style.transform = 'rotateY(0deg) rotateX(0deg)';
    });
  }

  // Door interaction
  const form = document.getElementById('choose-form');
  if (form) {
    const doors = Array.from(form.querySelectorAll('.door'));
    let submitting = false;

    doors.forEach(btn => {
      btn.addEventListener('click', (ev) => {
        if (submitting) {
          ev.preventDefault();
          return;
        }
        
        submitting = true;

        // Disable other door immediately
        doors.forEach(d => {
          if (d !== btn) d.disabled = true;
        });

        // Ripple effect
        const rect = btn.getBoundingClientRect();
        const ripple = document.createElement('span');
        ripple.className = 'ripple';
        const x = ev.clientX - rect.left;
        const y = ev.clientY - rect.top;
        ripple.style.left = (x - 20) + 'px';
        ripple.style.top = (y - 20) + 'px';
        ripple.style.width = ripple.style.height = '40px';
        btn.appendChild(ripple);

        // Open animation
        btn.classList.add('opening');

        // Ensure clicked value is sent
        const hidden = document.createElement('input');
        hidden.type = 'hidden';
        hidden.name = btn.name;
        hidden.value = btn.value;
        form.appendChild(hidden);

        // Submit after animation
        setTimeout(() => form.submit(), 800);
      });
    });
  }

  // Handle win/loss animations
  const last = {{ (last|tojson) if last else 'null' }};
  if (last) {
    if (last.outcome === "WIN") {
      // Show win animation
      const overlay = document.getElementById('result-overlay');
      const message = document.getElementById('result-message');
      overlay.style.opacity = '1';
      message.textContent = 'CORRECT!';
      message.classList.add('win-message');
      
      // Create particles
      createParticles(40, last.pick === 'life' ? '#32ff9d' : '#7aa8ff');
      
      // Show streak indicator if applicable
      const streak = {{ session.get('wins', 0) }};
      if (streak > 1) {
        const indicator = document.getElementById('streak-indicator');
        const count = document.getElementById('streak-count');
        count.textContent = streak;
        indicator.classList.add('active');
        
        // Auto-hide after 3 seconds
        setTimeout(() => {
          indicator.classList.remove('active');
        }, 3000);
      }
      
      // Confetti
      const confetti = document.createElement('div');
      confetti.className = 'confetti';
      const colors = ['#32ff9d', '#7aa8ff', '#f7d774', '#ff5a6e', '#a78bfa'];
      
      for (let i = 0; i < 50; i++) {
        const piece = document.createElement('i');
        piece.style.left = Math.random() * 100 + 'vw';
        piece.style.background = colors[Math.floor(Math.random() * colors.length)];
        piece.style.animationDelay = (Math.random() * 0.5) + 's';
        piece.style.animationDuration = (1 + Math.random() * 1.5) + 's';
        confetti.appendChild(piece);
      }
      
      document.body.appendChild(confetti);
      setTimeout(() => confetti.remove(), 2000);
      
      // Hide message after delay
      setTimeout(() => {
        overlay.style.opacity = '0';
      }, 1500);
    } else {
      // Show loss animation
      const overlay = document.getElementById('result-overlay');
      const message = document.getElementById('result-message');
      overlay.style.opacity = '1';
      message.textContent = 'WRONG!';
      message.classList.add('loss-message');
      
      // Create particles
      createParticles(30, '#ff5a6e');
      
      // Hide message after delay
      setTimeout(() => {
        overlay.style.opacity = '0';
      }, 1500);
    }
  }
  
  // Show current streak on page load if applicable
  const streak = {{ session.get('wins', 0) }};
  if (streak > 1) {
    const indicator = document.getElementById('streak-indicator');
    const count = document.getElementById('streak-count');
    count.textContent = streak;
    indicator.classList.add('active');
    
    // Auto-hide after 3 seconds
    setTimeout(() => {
      indicator.classList.remove('active');
    }, 3000);
  }
  
  // Function to create floating particles
  function createParticles(count, color) {
    for (let i = 0; i < count; i++) {
      const particle = document.createElement('div');
      particle.className = 'particle';
      particle.style.background = color;
      particle.style.width = (4 + Math.random() * 8) + 'px';
      particle.style.height = particle.style.width;
      particle.style.borderRadius = '50%';
      particle.style.left = '50%';
      particle.style.top = '50%';
      particle.style.setProperty('--tx', (Math.random() * 200 - 100) + 'px');
      particle.style.setProperty('--ty', (Math.random() * 200 - 100) + 'px');
      document.body.appendChild(particle);
      
      // Remove particle after animation completes
      setTimeout(() => {
        particle.remove();
      }, 1500);
    }
  }
})();
</script>
</body>
</html>
    """, game_over=game_over, last=last, progress_pct=progress_pct)

@app.route("/choose", methods=["POST"])
def choose():
    if "round" not in session:
        reset_run()
        session["attempts"] = 0

    if session["round"] > 10:
        return redirect(url_for("home"))

    pick = request.form.get("door")
    correct = session.get("correct_door")

    # Evaluate
    if correct is None:
        outcome = "LOSS"
    else:
        outcome = "WIN" if pick == correct else "LOSS"

    session["history"].append({
        "round": session["round"],
        "pick": pick,
        "outcome": outcome,
        "correct_door": correct
    })
    session["last"] = {"pick": pick, "correct": correct, "outcome": outcome}

    if outcome == "WIN":
        session["wins"] += 1
        session["round"] += 1
        if session["wins"] >= 10:
            session["banner"] = "🎉 You cleared all 10 rounds in a row!"
            session["round"] = 11
        return redirect(url_for("home"))
    else:
        start_new_attempt(reason="❌ Wrong guess. Run has been reset to Round 1.")
        return redirect(url_for("home"))

@app.route("/hard-reset")
def hard_reset():
    reset_run()
    session["attempts"] = 0
    session["requests_sent"] = False  # Reset the requests flag
    return redirect(url_for("home"))

# Beacon endpoints (204, no-store)
@app.get("/QU9IRntMMWYzXzByX0QzNHRoXw")
def QU9IRntMMWYzXzByX0QzNHRoXw():
    return _empty_204()

@app.get("/VGgzX0c0bTNfMGZfQ2gwMWMzc180bmRf")
def VGgzX0c0bTNfMGZfQ2gwMWMzc180bmRf():
    return _empty_204()

@app.get("/VGgzX0NoMDFjM19XNHNfTjN2M3JfWTB1cnN9")
def VGgzX0NoMDFjM19XNHNfTjN2M3JfWTB1cnN9():
    return _empty_204()





# Debug state
@app.route("/state")
def state():
    data = {k: v for k, v in session.items()}
    return jsonify(data)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
