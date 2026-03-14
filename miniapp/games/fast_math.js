/**
 * Fast Math Game
 * Quick math problems with combo multipliers
 */

import { sounds } from '../lib/sounds.js';

class FastMathGame {
  constructor(container, options = {}) {
    this.container = container;
    this.difficulty = options.difficulty || 'easy';
    this.totalQuestions = 20;
    this.currentQuestion = 0;
    this.score = 0;
    this.combo = 0;
    this.maxCombo = 0;
    this.correctCount = 0;
    this.timer = null;
    this.timeLeft = 5;
    this.gameActive = false;
    this.onComplete = options.onComplete || (() => {});

    sounds.preload(['tick', 'correct', 'wrong', 'levelup', 'gameover']);
  }

  start() {
    this.gameActive = true;
    this.currentQuestion = 0;
    this.score = 0;
    this.combo = 0;
    this.maxCombo = 0;
    this.correctCount = 0;
    this.showQuestion();
  }

  generateQuestion() {
    const ranges = {
      easy: { min: 1, max: 10 },
      medium: { min: 1, max: 50 },
      hard: { min: 1, max: 100 },
      expert: { min: 1, max: 100 }
    };

    const range = ranges[this.difficulty];
    const operations = this.difficulty === 'expert'
      ? ['+', '-', '*', '/']
      : ['+', '-'];

    const op = operations[Math.floor(Math.random() * operations.length)];
    let a = Math.floor(Math.random() * (range.max - range.min + 1)) + range.min;
    let b = Math.floor(Math.random() * (range.max - range.min + 1)) + range.min;
    let answer;

    // Ensure clean division and positive results
    if (op === '/') {
      answer = Math.floor(Math.random() * 10) + 1;
      b = answer;
      a = a * b;
    } else if (op === '-') {
      if (a < b) [a, b] = [b, a];
      answer = a - b;
    } else if (op === '*') {
      b = Math.floor(Math.random() * 12) + 1;
      answer = a * b;
    } else {
      answer = a + b;
    }

    const opSymbols = { '+': '+', '-': '−', '*': '×', '/': '÷' };

    return {
      text: `${a} ${opSymbols[op]} ${b} = ?`,
      answer: answer,
      options: this.generateOptions(answer)
    };
  }

  generateOptions(correct) {
    const options = [correct];
    while (options.length < 4) {
      const offset = Math.floor(Math.random() * 10) - 5;
      const wrong = correct + offset;
      if (wrong !== correct && wrong >= 0 && !options.includes(wrong)) {
        options.push(wrong);
      }
    }
    return options.sort(() => Math.random() - 0.5);
  }

  showQuestion() {
    if (this.currentQuestion >= this.totalQuestions) {
      this.endGame();
      return;
    }

    const q = this.generateQuestion();
    this.timeLeft = 5;

    this.container.innerHTML = `
      <div style="text-align: center; padding: 20px;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 20px;">
          <span style="font-size: 14px; color: var(--text-muted);">Q${this.currentQuestion + 1}/${this.totalQuestions}</span>
          <span style="font-size: 14px; color: var(--accent);">Score: ${this.score}</span>
        </div>

        ${this.combo > 1 ? `
          <div style="font-size: 18px; color: var(--warning); margin-bottom: 10px;">
            🔥 Combo x${this.combo}!
          </div>
        ` : ''}

        <div style="font-size: 48px; font-weight: bold; margin: 30px 0; font-family: monospace;">
          ${q.text}
        </div>

        <div class="timer-bar" style="width: 100%; height: 8px; background: var(--bg-input); border-radius: 4px; margin-bottom: 30px;">
          <div class="timer-fill" style="width: 100%; height: 100%; background: var(--accent); transition: width 0.1s linear;"></div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px;">
          ${q.options.map((opt, i) => `
            <button class="math-option" data-value="${opt}" style="
              padding: 20px;
              font-size: 24px;
              font-weight: bold;
              background: var(--bg-input);
              border: 2px solid var(--border);
              border-radius: var(--r-lg);
              cursor: pointer;
              transition: all 0.2s;
            ">${opt}</button>
          `).join('')}
        </div>
      </div>
    `;

    this.container.querySelectorAll('.math-option').forEach(btn => {
      btn.addEventListener('click', () => this.handleAnswer(parseInt(btn.dataset.value), q.answer));
    });

    this.startTimer();
  }

  startTimer() {
    const startTime = Date.now();
    const duration = 5000;

    this.timer = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const remaining = Math.max(0, duration - elapsed);
      const percent = (remaining / duration) * 100;

      const fill = this.container.querySelector('.timer-fill');
      if (fill) {
        fill.style.width = percent + '%';
        if (percent < 30) fill.style.background = 'var(--danger)';
      }

      if (elapsed > 0 && elapsed < duration && Math.floor(elapsed / 1000) > Math.floor((elapsed - 100) / 1000)) {
        sounds.play('tick');
      }

      if (remaining <= 0) {
        this.handleTimeout();
      }
    }, 100);
  }

  handleAnswer(selected, correct) {
    if (!this.gameActive) return;
    clearInterval(this.timer);

    const isCorrect = selected === correct;
    const buttons = this.container.querySelectorAll('.math-option');

    buttons.forEach(btn => {
      const val = parseInt(btn.dataset.value);
      if (val === correct) {
        btn.style.background = 'var(--success-dim)';
        btn.style.borderColor = 'var(--success)';
      } else if (val === selected && !isCorrect) {
        btn.style.background = 'var(--danger-dim)';
        btn.style.borderColor = 'var(--danger)';
      }
      btn.disabled = true;
    });

    if (isCorrect) {
      this.combo++;
      this.maxCombo = Math.max(this.maxCombo, this.combo);
      this.correctCount++;

      // Points: base 100 + combo bonus
      const points = 100 + (this.combo * 10);
      this.score += points;

      sounds.play('correct');

      if (this.combo > 1 && this.combo % 5 === 0) {
        sounds.play('levelup');
      }
    } else {
      this.combo = 0;
      sounds.play('wrong');
    }

    setTimeout(() => {
      this.currentQuestion++;
      this.showQuestion();
    }, 800);
  }

  handleTimeout() {
    if (!this.gameActive) return;
    clearInterval(this.timer);
    this.combo = 0;
    sounds.play('wrong');

    setTimeout(() => {
      this.currentQuestion++;
      this.showQuestion();
    }, 800);
  }

  endGame() {
    this.gameActive = false;
    const accuracy = Math.round((this.correctCount / this.totalQuestions) * 100);

    if (accuracy >= 70) {
      sounds.play('victory');
    } else {
      sounds.play('gameover');
    }

    this.container.innerHTML = `
      <div style="text-align: center; padding: 40px 20px;">
        <div style="font-size: 64px; margin-bottom: 20px;">${accuracy >= 80 ? '🧮🎉' : accuracy >= 60 ? '🧮👍' : '🧮💪'}</div>
        <h2 style="margin-bottom: 20px;">Math Challenge Complete!</h2>

        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin: 30px 0;">
          <div style="background: var(--bg-input); padding: 15px; border-radius: var(--r-lg);">
            <div style="font-size: 24px; color: var(--accent); font-weight: bold;">${this.score}</div>
            <div style="font-size: 12px; color: var(--text-muted);">Total Score</div>
          </div>
          <div style="background: var(--bg-input); padding: 15px; border-radius: var(--r-lg);">
            <div style="font-size: 24px; color: var(--warning); font-weight: bold;">x${this.maxCombo}</div>
            <div style="font-size: 12px; color: var(--text-muted);">Max Combo</div>
          </div>
          <div style="background: var(--bg-input); padding: 15px; border-radius: var(--r-lg);">
            <div style="font-size: 24px; color: var(--success); font-weight: bold;">${accuracy}%</div>
            <div style="font-size: 12px; color: var(--text-muted);">Accuracy</div>
          </div>
          <div style="background: var(--bg-input); padding: 15px; border-radius: var(--r-lg);">
            <div style="font-size: 24px; color: var(--accent); font-weight: bold;">${this.correctCount}/${this.totalQuestions}</div>
            <div style="font-size: 12px; color: var(--text-muted);">Correct</div>
          </div>
        </div>

        <button id="play-again-btn" style="padding: 15px 40px; background: var(--accent); border: none; border-radius: var(--r-lg); font-size: 18px; cursor: pointer;">
          Play Again
        </button>
      </div>
    `;

    this.container.querySelector('#play-again-btn').addEventListener('click', () => {
      sounds.play('click');
      this.start();
    });

    this.onComplete({ score: this.score, accuracy, maxCombo: this.maxCombo, gameType: 'fast_math' });
  }
}

export { FastMathGame };
export default FastMathGame;
