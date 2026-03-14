/**
 * Sound manager for Nexus Bot games
 * All sounds play client-side, zero server bandwidth
 * Auto-rotates between variants for variety
 */

class SoundManager {
  constructor() {
    this.enabled = localStorage.getItem('sounds_enabled') !== 'false';
    this.volume = parseFloat(localStorage.getItem('sounds_volume') || '0.7');
    this.cache = {}; // preloaded Audio objects
    this.basePath = '/sounds/';

    // Sound variants for variety (using WAV format)
    this.variants = {
      correct: ['trivia/correct1.wav', 'trivia/correct2.wav', 'trivia/correct3.wav'],
      wrong: ['trivia/wrong1.wav', 'trivia/wrong2.wav'],
      victory: ['general/victory.wav'],
      gameover: ['general/gameover.wav'],
      levelup: ['general/levelup.wav'],
      click: ['general/click.wav'],
      countdown: ['general/countdown.wav'],
      tick: ['general/tick.wav'],
      dice: ['dice/roll1.wav', 'dice/roll2.wav'],
      coins: ['dice/coins.wav'],
      jackpot: ['dice/coins.wav'], // Use coins as jackpot
      cardflip: ['cards/flip.wav'],
      shuffle: ['cards/shuffle.wav'],
      deal: ['cards/shuffle.wav'], // Use shuffle as deal
      win: ['cards/win.wav'],
      lose: ['general/gameover.wav'], // Use gameover as lose
      move: ['general/click.wav'], // Use click as move
      attack: ['general/click.wav'],
      build: ['general/levelup.wav'],
      defeat: ['general/gameover.wav'],
      math_correct: ['math/correct.wav'],
      math_wrong: ['math/wrong.wav'],
      timeup: ['trivia/timeout.wav'],
      word_correct: ['word/correct.wav'],
      word_wrong: ['word/wrong.wav'],
      hint: ['general/countdown.wav'],
      complete: ['word/complete.wav'],
      suspense: ['trivia/timeout.wav'],
      final_answer: ['trivia/correct1.wav'],
      timeout: ['trivia/timeout.wav'],
      daily_bonus: ['general/victory.wav'],
    };

    this._lastUsed = {}; // track last used variant per type
  }

  /**
   * Play a sound with auto-rotation between variants
   * @param {string} type - Sound type (e.g., 'correct', 'click')
   * @returns {Promise<void>}
   */
  async play(type) {
    if (!this.enabled) return;

    const variants = this.variants[type];
    if (!variants || variants.length === 0) {
      console.warn(`[SOUNDS] Unknown sound type: ${type}`);
      return;
    }

    // Pick a variant (rotate to avoid repetition)
    let variantIndex = 0;
    if (variants.length > 1) {
      const lastUsed = this._lastUsed[type] || 0;
      variantIndex = (lastUsed + 1) % variants.length;
      this._lastUsed[type] = variantIndex;
    }

    const soundPath = this.basePath + variants[variantIndex];

    try {
      // Use cached audio or create new
      let audio = this.cache[soundPath];
      if (!audio) {
        audio = new Audio(soundPath);
        audio.preload = 'auto';
        this.cache[soundPath] = audio;
      }

      // Reset and set volume
      audio.currentTime = 0;
      audio.volume = this.volume;

      // Play with autoplay policy handling
      const playPromise = audio.play();
      if (playPromise !== undefined) {
        playPromise.catch((error) => {
          // Autoplay blocked - ignore silently
          if (error.name === 'NotAllowedError') {
            console.debug('[SOUNDS] Autoplay blocked by browser policy');
          } else {
            console.warn('[SOUNDS] Play error:', error);
          }
        });
      }
    } catch (error) {
      console.warn('[SOUNDS] Error playing sound:', error);
    }
  }

  /**
   * Preload sounds for a game to avoid delay
   * @param {string[]} types - Array of sound types to preload
   */
  preload(types) {
    if (!this.enabled) return;

    types.forEach((type) => {
      const variants = this.variants[type];
      if (!variants) return;

      variants.forEach((variant) => {
        const path = this.basePath + variant;
        if (!this.cache[path]) {
          const audio = new Audio(path);
          audio.preload = 'auto';
          this.cache[path] = audio;
        }
      });
    });
  }

  /**
   * Toggle sounds on/off
   * @returns {boolean} New enabled state
   */
  toggle() {
    this.enabled = !this.enabled;
    localStorage.setItem('sounds_enabled', this.enabled.toString());

    // Play test sound if enabling
    if (this.enabled) {
      this.play('click');
    }

    return this.enabled;
  }

  /**
   * Set volume level
   * @param {number} v - Volume 0-1
   */
  setVolume(v) {
    this.volume = Math.max(0, Math.min(1, v));
    localStorage.setItem('sounds_volume', this.volume.toString());

    // Update all cached audio elements
    Object.values(this.cache).forEach((audio) => {
      audio.volume = this.volume;
    });
  }

  /**
   * Get current enabled state
   * @returns {boolean}
   */
  isEnabled() {
    return this.enabled;
  }

  /**
   * Get current volume
   * @returns {number}
   */
  getVolume() {
    return this.volume;
  }

  /**
   * Create a sound toggle button element
   * @returns {HTMLElement}
   */
  createToggleButton() {
    const btn = document.createElement('button');
    btn.className = 'sound-toggle-btn';
    btn.style.cssText = `
      background: none;
      border: none;
      font-size: 20px;
      cursor: pointer;
      padding: 8px;
      border-radius: 50%;
      transition: background 0.2s;
    `;

    const updateIcon = () => {
      btn.textContent = this.enabled ? '🔊' : '🔇';
      btn.title = this.enabled ? 'Sounds On (Click to mute)' : 'Sounds Off (Click to unmute)';
    };

    updateIcon();

    btn.addEventListener('click', () => {
      this.toggle();
      updateIcon();
      btn.style.background = 'var(--bg-hover)';
      setTimeout(() => {
        btn.style.background = 'none';
      }, 200);
    });

    return btn;
  }
}

// Export singleton instance
export const sounds = new SoundManager();
export default sounds;
