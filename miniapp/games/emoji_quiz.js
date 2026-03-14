/**
 * Emoji Quiz Game
 * Guess movies, songs, countries from emoji combinations
 */

import { sounds } from '../lib/sounds.js';

// 100+ built-in questions
const QUESTIONS = [
  // Movies (30 questions)
  { emojis: '🦁👑', answer: 'The Lion King', category: 'Movies', options: ['The Lion King', 'Madagascar', 'Zootopia', 'Jungle Book'] },
  { emojis: '🚢❄️🎭', answer: 'Titanic', category: 'Movies', options: ['Titanic', 'The Poseidon Adventure', 'Life of Pi', 'Moby Dick'] },
  { emojis: '🕷️👨', answer: 'Spider-Man', category: 'Movies', options: ['Spider-Man', 'Ant-Man', 'Batman', 'Iron Man'] },
  { emojis: '🧙‍♂️💍', answer: 'Lord of the Rings', category: 'Movies', options: ['Lord of the Rings', 'Harry Potter', 'The Hobbit', 'Narnia'] },
  { emojis: '🦕🦖', answer: 'Jurassic Park', category: 'Movies', options: ['Jurassic Park', 'The Land Before Time', 'Dinosaur', 'King Kong'] },
  { emojis: '🚀🌌', answer: 'Star Wars', category: 'Movies', options: ['Star Wars', 'Star Trek', 'Gravity', 'Interstellar'] },
  { emojis: '👽📞', answer: 'E.T.', category: 'Movies', options: ['E.T.', 'Close Encounters', 'Signs', 'Arrival'] },
  { emojis: '🏴‍☠️⚓', answer: 'Pirates of the Caribbean', category: 'Movies', options: ['Pirates of the Caribbean', 'Treasure Island', 'Peter Pan', 'Hook'] },
  { emojis: '🤖🚗', answer: 'Transformers', category: 'Movies', options: ['Transformers', 'Cars', 'Herbie', 'Knight Rider'] },
  { emojis: '🦇🃏', answer: 'The Dark Knight', category: 'Movies', options: ['The Dark Knight', 'Batman Begins', 'Joker', 'Suicide Squad'] },
  { emojis: '⚡⚡', answer: 'Harry Potter', category: 'Movies', options: ['Harry Potter', 'Percy Jackson', 'Fantastic Beasts', 'The Sorcerer\'s Apprentice'] },
  { emojis: '🧊👸', answer: 'Frozen', category: 'Movies', options: ['Frozen', 'Ice Age', 'The Snow Queen', 'Tangled'] },
  { emojis: '🤠👢', answer: 'Toy Story', category: 'Movies', options: ['Toy Story', 'Cowboys & Aliens', 'The Lone Ranger', 'Rango'] },
  { emojis: '📱💀', answer: 'The Ring', category: 'Movies', options: ['The Ring', 'One Missed Call', 'Pulse', 'The Grudge'] },
  { emojis: '🧟‍♂️🧠', answer: 'The Walking Dead', category: 'Movies', options: ['The Walking Dead', 'World War Z', 'Shaun of the Dead', 'Zombieland'] },
  { emojis: '🎈🤡', answer: 'It', category: 'Movies', options: ['It', 'Killer Klowns', 'Poltergeist', 'The Conjuring'] },
  { emojis: '⏰🐇', answer: 'Alice in Wonderland', category: 'Movies', options: ['Alice in Wonderland', 'The White Rabbit', 'Through the Looking Glass', 'Pan\'s Labyrinth'] },
  { emojis: '🦹‍♀️❤️🦹‍♂️', answer: 'Suicide Squad', category: 'Movies', options: ['Suicide Squad', 'Birds of Prey', 'Guardians of the Galaxy', 'The Avengers'] },
  { emojis: '🐠🔍', answer: 'Finding Nemo', category: 'Movies', options: ['Finding Nemo', 'Shark Tale', 'The Little Mermaid', 'Aquaman'] },
  { emojis: '🚗⚡', answer: 'Back to the Future', category: 'Movies', options: ['Back to the Future', 'The Time Machine', 'Looper', 'Terminator'] },
  { emojis: '👰‍♀️🔪', answer: 'Kill Bill', category: 'Movies', options: ['Kill Bill', 'Bride of Chucky', 'Ready or Not', 'The Bride'] },
  { emojis: '🏰👧🐉', answer: 'How to Train Your Dragon', category: 'Movies', options: ['How to Train Your Dragon', 'Shrek', 'Brave', 'The Dragon Prince'] },
  { emojis: '🎭👻', answer: 'Phantom of the Opera', category: 'Movies', options: ['Phantom of the Opera', 'The Mask', 'Moulin Rouge', 'Les Misérables'] },
  { emojis: '👠👑', answer: 'Cinderella', category: 'Movies', options: ['Cinderella', 'The Princess Diaries', 'Enchanted', 'Ever After'] },
  { emojis: '🧸🍯', answer: 'Winnie the Pooh', category: 'Movies', options: ['Winnie the Pooh', 'Ted', 'Paddington', 'Christopher Robin'] },
  { emojis: '🎪🤡', answer: 'The Greatest Showman', category: 'Movies', options: ['The Greatest Showman', 'Dumbo', 'Water for Elephants', 'Circus'] },
  { emojis: '🦊🐰', answer: 'Zootopia', category: 'Movies', options: ['Zootopia', 'Fantastic Mr. Fox', 'Robin Hood', 'Chicken Run'] },
  { emojis: '🏃‍♂️🏃‍♀️💰', answer: 'Ocean\'s Eleven', category: 'Movies', options: ['Ocean\'s Eleven', 'The Italian Job', 'Now You See Me', 'Inside Man'] },
  { emojis: '🎤👨‍🎤', answer: 'Bohemian Rhapsody', category: 'Movies', options: ['Bohemian Rhapsody', 'Rocketman', 'A Star is Born', 'Elvis'] },
  { emojis: '🎮👾', answer: 'Wreck-It Ralph', category: 'Movies', options: ['Wreck-It Ralph', 'Pixels', 'Ready Player One', 'The Lego Movie'] },

  // Songs (20 questions)
  { emojis: '🔥💃', answer: 'Firework', category: 'Songs', options: ['Firework', 'Dynamite', 'Burning Up', 'Hot N Cold'] },
  { emojis: '🎵👶', answer: 'Baby', category: 'Songs', options: ['Baby', 'Baby One More Time', 'Rock-a-Bye Baby', 'Ice Ice Baby'] },
  { emojis: '🌧️💜', answer: 'Purple Rain', category: 'Songs', options: ['Purple Rain', 'November Rain', 'Set Fire to the Rain', 'Rain on Me'] },
  { emojis: '👑👑👑', answer: 'We Are The Champions', category: 'Songs', options: ['We Are The Champions', 'Killer Queen', 'Radio Ga Ga', 'Another One Bites the Dust'] },
  { emojis: '🚁🎸', answer: 'Stairway to Heaven', category: 'Songs', options: ['Stairway to Heaven', 'Highway to Hell', 'Learning to Fly', 'Fly Away'] },
  { emojis: '🌶️🌶️🌶️', answer: 'Spice Up Your Life', category: 'Songs', options: ['Spice Up Your Life', 'Hot Stuff', 'Spicy', 'Red Hot Chili Peppers'] },
  { emojis: '👀🐯', answer: 'Eye of the Tiger', category: 'Songs', options: ['Eye of the Tiger', 'Roar', 'The Lion Sleeps Tonight', 'Welcome to the Jungle'] },
  { emojis: '🌙🚶', answer: 'Moonwalk', category: 'Songs', options: ['Moonwalk', 'Walking on the Moon', 'Bad Moon Rising', 'Dancing in the Moonlight'] },
  { emojis: '🎄🎅', answer: 'All I Want for Christmas', category: 'Songs', options: ['All I Want for Christmas', 'Last Christmas', 'Jingle Bells', 'White Christmas'] },
  { emojis: '👸❄️', answer: 'Let It Go', category: 'Songs', options: ['Let It Go', 'Do You Want to Build a Snowman', 'Into the Unknown', 'Show Yourself'] },
  { emojis: '🎵🌍', answer: 'We Are the World', category: 'Songs', options: ['We Are the World', 'Heal the World', 'Earth Song', 'What a Wonderful World'] },
  { emojis: '🕺🪩', answer: 'Stayin\' Alive', category: 'Songs', options: ['Stayin\' Alive', 'Dancing Queen', 'Y.M.C.A.', 'Night Fever'] },
  { emojis: '🚕🗽', answer: 'Empire State of Mind', category: 'Songs', options: ['Empire State of Mind', 'New York New York', 'Welcome to New York', 'Englishman in New York'] },
  { emojis: '🌊👋', answer: 'Waves', category: 'Songs', options: ['Waves', 'Surfin\' USA', 'Wipe Out', 'Under the Sea'] },
  { emojis: '💔📞', answer: 'Hello', category: 'Songs', options: ['Hello', 'Someone Like You', 'Rolling in the Deep', 'Set Fire to the Rain'] },
  { emojis: '⭐🌟', answer: 'Shooting Star', category: 'Songs', options: ['Shooting Star', 'Starboy', 'Counting Stars', 'Yellow'] },
  { emojis: '🎸🤘', answer: 'Sweet Child O\' Mine', category: 'Songs', options: ['Sweet Child O\' Mine', 'November Rain', 'Paradise City', 'Welcome to the Jungle'] },
  { emojis: '🌈🦄', answer: 'Rainbow', category: 'Songs', options: ['Rainbow', 'Somewhere Over the Rainbow', 'True Colors', 'Colors of the Wind'] },
  { emojis: '🕰️⏰', answer: 'Time After Time', category: 'Songs', options: ['Time After Time', 'Clocks', 'Time', 'As Time Goes By'] },
  { emojis: '🚗🛣️', answer: 'Life is a Highway', category: 'Songs', options: ['Life is a Highway', 'Route 66', 'Highway to Hell', 'Born to be Wild'] },

  // Countries (20 questions)
  { emojis: '🗽🍎', answer: 'United States', category: 'Countries', options: ['United States', 'Canada', 'Mexico', 'United Kingdom'] },
  { emojis: '🥖🗼', answer: 'France', category: 'Countries', options: ['France', 'Italy', 'Spain', 'Germany'] },
  { emojis: '🍕🏛️', answer: 'Italy', category: 'Countries', options: ['Italy', 'Greece', 'Spain', 'Portugal'] },
  { emojis: '🍣🗻', answer: 'Japan', category: 'Countries', options: ['Japan', 'China', 'South Korea', 'Thailand'] },
  { emojis: '🦘🦘', answer: 'Australia', category: 'Countries', options: ['Australia', 'New Zealand', 'South Africa', 'Kenya'] },
  { emojis: '🐂💃', answer: 'Spain', category: 'Countries', options: ['Spain', 'Mexico', 'Argentina', 'Brazil'] },
  { emojis: '🍁🦌', answer: 'Canada', category: 'Countries', options: ['Canada', 'United States', 'Russia', 'Norway'] },
  { emojis: '🐼🎋', answer: 'China', category: 'Countries', options: ['China', 'Japan', 'South Korea', 'Vietnam'] },
  { emojis: '🦁🦒', answer: 'South Africa', category: 'Countries', options: ['South Africa', 'Kenya', 'Tanzania', 'Egypt'] },
  { emojis: '🏰🍺', answer: 'Germany', category: 'Countries', options: ['Germany', 'Austria', 'Czech Republic', 'Belgium'] },
  { emojis: '🦅🗿', answer: 'Mexico', category: 'Countries', options: ['Mexico', 'Peru', 'Colombia', 'Chile'] },
  { emojis: '🐅🕌', answer: 'India', category: 'Countries', options: ['India', 'Pakistan', 'Bangladesh', 'Sri Lanka'] },
  { emojis: '🦌❄️', answer: 'Norway', category: 'Countries', options: ['Norway', 'Sweden', 'Finland', 'Iceland'] },
  { emojis: '🐨🌊', answer: 'New Zealand', category: 'Countries', options: ['New Zealand', 'Australia', 'Fiji', 'Samoa'] },
  { emojis: '🌮🌵', answer: 'Mexico', category: 'Countries', options: ['Mexico', 'Texas', 'Arizona', 'California'] },
  { emojis: '🏔️🕰️', answer: 'Switzerland', category: 'Countries', options: ['Switzerland', 'Austria', 'France', 'Italy'] },
  { emojis: '🗿🌺', answer: 'Easter Island', category: 'Countries', options: ['Easter Island', 'Hawaii', 'Fiji', 'Samoa'] },
  { emojis: '🐫🕌', answer: 'Saudi Arabia', category: 'Countries', options: ['Saudi Arabia', 'UAE', 'Qatar', 'Kuwait'] },
  { emojis: '🌷🚲', answer: 'Netherlands', category: 'Countries', options: ['Netherlands', 'Belgium', 'Denmark', 'Luxembourg'] },
  { emojis: '🥝🌿', answer: 'New Zealand', category: 'Countries', options: ['New Zealand', 'Australia', 'Fiji', 'Samoa'] },

  // Food (15 questions)
  { emojis: '🍔🍟', answer: 'Fast Food', category: 'Food', options: ['Fast Food', 'Burger King', 'McDonald\'s', 'Junk Food'] },
  { emojis: '🍕🧀', answer: 'Pizza', category: 'Food', options: ['Pizza', 'Pasta', 'Lasagna', 'Calzone'] },
  { emojis: '🌮🌯', answer: 'Mexican Food', category: 'Food', options: ['Mexican Food', 'Tacos', 'Burritos', 'Tex-Mex'] },
  { emojis: '🍣🍱', answer: 'Sushi', category: 'Food', options: ['Sushi', 'Japanese Food', 'Rice Bowls', 'Bento'] },
  { emojis: '🥐☕', answer: 'Breakfast', category: 'Food', options: ['Breakfast', 'Brunch', 'Continental', 'Morning'] },
  { emojis: '🍦🍨', answer: 'Ice Cream', category: 'Food', options: ['Ice Cream', 'Frozen Yogurt', 'Gelato', 'Sorbet'] },
  { emojis: '🍝🍷', answer: 'Italian Dinner', category: 'Food', options: ['Italian Dinner', 'Pasta Night', 'Date Night', 'Romantic Dinner'] },
  { emojis: '🥗🥑', answer: 'Healthy Food', category: 'Food', options: ['Healthy Food', 'Salad', 'Vegan', 'Organic'] },
  { emojis: '🍩☕', answer: 'Coffee Break', category: 'Food', options: ['Coffee Break', 'Dessert', 'Snack Time', 'Tea Time'] },
  { emojis: '🍗🍺', answer: 'Wings and Beer', category: 'Food', options: ['Wings and Beer', 'Sports Bar', 'Game Day', 'Pub Food'] },
  { emojis: '🥞🍯', answer: 'Pancakes', category: 'Food', options: ['Pancakes', 'Waffles', 'French Toast', 'Crepes'] },
  { emojis: '🍜🥢', answer: 'Ramen', category: 'Food', options: ['Ramen', 'Noodles', 'Pho', 'Udon'] },
  { emojis: '🦞🧈', answer: 'Lobster', category: 'Food', options: ['Lobster', 'Crab', 'Seafood', 'Shellfish'] },
  { emojis: '🍰🎂', answer: 'Cake', category: 'Food', options: ['Cake', 'Dessert', 'Birthday', 'Pastry'] },
  { emojis: '🥡🥠', answer: 'Chinese Takeout', category: 'Food', options: ['Chinese Takeout', 'Delivery', 'Noodles', 'Fortune Cookie'] },

  // Animals (15 questions)
  { emojis: '🦁👑', answer: 'Lion King', category: 'Animals', options: ['Lion King', 'Alpha Lion', 'Pride Leader', 'Jungle King'] },
  { emojis: '🐼🎋', answer: 'Panda', category: 'Animals', options: ['Panda', 'Bamboo Bear', 'China Bear', 'Red Panda'] },
  { emojis: '🦒🌳', answer: 'Giraffe', category: 'Animals', options: ['Giraffe', 'Tall One', 'Savanna', 'Long Neck'] },
  { emojis: '🐧❄️', answer: 'Penguin', category: 'Animals', options: ['Penguin', 'Antarctica', 'Ice Bird', 'Marching'] },
  { emojis: '🦅🇺🇸', answer: 'Bald Eagle', category: 'Animals', options: ['Bald Eagle', 'Golden Eagle', 'American Bird', 'National Symbol'] },
  { emojis: '🦈🌊', answer: 'Shark', category: 'Animals', options: ['Shark', 'Great White', 'Ocean Predator', 'Jaws'] },
  { emojis: '🦋🌸', answer: 'Butterfly', category: 'Animals', options: ['Butterfly', 'Moth', 'Caterpillar', 'Pollinator'] },
  { emojis: '🐘🌍', answer: 'Elephant', category: 'Animals', options: ['Elephant', 'Mammoth', 'Big Ears', 'Trumpet'] },
  { emojis: '🦉🌙', answer: 'Owl', category: 'Animals', options: ['Owl', 'Night Bird', 'Hoot', 'Wise One'] },
  { emojis: '🐙🌊', answer: 'Octopus', category: 'Animals', options: ['Octopus', 'Squid', 'Tentacles', 'Eight Arms'] },
  { emojis: '🦩🦩🦩', answer: 'Flamingo', category: 'Animals', options: ['Flamingo', 'Pink Bird', 'Tropical', 'Lawn Ornament'] },
  { emojis: '🐢🐢', answer: 'Turtle', category: 'Animals', options: ['Turtle', 'Tortoise', 'Slow', 'Shell'] },
  { emojis: '🦓🦓', answer: 'Zebra', category: 'Animals', options: ['Zebra', 'Stripes', 'Safari', 'African Horse'] },
  { emojis: '🦘👶', answer: 'Kangaroo', category: 'Animals', options: ['Kangaroo', 'Joey', 'Hop', 'Pouch'] },
  { emojis: '🦥🌿', answer: 'Sloth', category: 'Animals', options: ['Sloth', 'Slow', 'Lazy', 'Hanging'] },
];

class EmojiQuizGame {
  constructor(container, options = {}) {
    this.container = container;
    this.currentQuestion = 0;
    this.score = 0;
    this.questions = [];
    this.timer = null;
    this.timeLeft = 30;
    this.gameActive = false;
    this.totalQuestions = options.totalQuestions || 10;
    this.onComplete = options.onComplete || (() => {});

    // Preload sounds
    sounds.preload(['tick', 'correct', 'wrong', 'victory', 'gameover']);
  }

  start() {
    this.gameActive = true;
    this.currentQuestion = 0;
    this.score = 0;

    // Shuffle and select questions
    const shuffled = [...QUESTIONS].sort(() => Math.random() - 0.5);
    this.questions = shuffled.slice(0, this.totalQuestions);

    this.showQuestion();
  }

  showQuestion() {
    if (this.currentQuestion >= this.questions.length) {
      this.endGame();
      return;
    }

    const q = this.questions[this.currentQuestion];
    this.timeLeft = 30;

    this.container.innerHTML = `
      <div class="emoji-quiz-game" style="text-align: center; padding: 20px;">
        <div style="margin-bottom: 20px;">
          <span style="font-size: 14px; color: var(--text-muted);">
            Question ${this.currentQuestion + 1}/${this.totalQuestions} • Score: ${this.score}
          </span>
        </div>

        <div style="font-size: 64px; margin: 30px 0; letter-spacing: 10px;">
          ${q.emojis}
        </div>

        <div style="font-size: 14px; color: var(--accent); margin-bottom: 20px;">
          Category: ${q.category}
        </div>

        <div class="timer-bar" style="
          width: 100%;
          height: 8px;
          background: var(--bg-input);
          border-radius: 4px;
          margin-bottom: 30px;
          overflow: hidden;
        ">
          <div class="timer-fill" style="
            width: 100%;
            height: 100%;
            background: var(--accent);
            transition: width 1s linear;
          "></div>
        </div>

        <div class="options" style="display: grid; gap: 12px;">
          ${q.options.map((opt, i) => `
            <button class="quiz-option" data-index="${i}" style="
              padding: 15px 20px;
              background: var(--bg-input);
              border: 2px solid var(--border);
              border-radius: var(--r-lg);
              font-size: 16px;
              cursor: pointer;
              transition: all 0.2s;
            ">${opt}</button>
          `).join('')}
        </div>
      </div>
    `;

    // Add event listeners
    this.container.querySelectorAll('.quiz-option').forEach(btn => {
      btn.addEventListener('click', (e) => this.handleAnswer(e.target));
    });

    // Start timer
    this.startTimer();

    // Play countdown tick every second
    this.tickInterval = setInterval(() => {
      if (this.timeLeft > 0 && this.gameActive) {
        sounds.play('tick');
      }
    }, 1000);
  }

  startTimer() {
    const timerFill = this.container.querySelector('.timer-fill');
    const startTime = Date.now();
    const duration = 30000; // 30 seconds

    this.timer = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const remaining = Math.max(0, duration - elapsed);
      const percent = (remaining / duration) * 100;

      if (timerFill) {
        timerFill.style.width = percent + '%';
        if (percent < 30) {
          timerFill.style.background = 'var(--danger)';
        }
      }

      if (remaining <= 0) {
        this.handleTimeout();
      }
    }, 100);
  }

  handleAnswer(button) {
    if (!this.gameActive) return;

    clearInterval(this.timer);
    clearInterval(this.tickInterval);

    const q = this.questions[this.currentQuestion];
    const selected = button.textContent;
    const isCorrect = selected === q.answer;

    // Show feedback
    const buttons = this.container.querySelectorAll('.quiz-option');
    buttons.forEach(btn => {
      if (btn.textContent === q.answer) {
        btn.style.background = 'var(--success-dim)';
        btn.style.borderColor = 'var(--success)';
        btn.style.color = 'var(--success)';
      } else if (btn === button && !isCorrect) {
        btn.style.background = 'var(--danger-dim)';
        btn.style.borderColor = 'var(--danger)';
        btn.style.color = 'var(--danger)';
      }
      btn.disabled = true;
    });

    if (isCorrect) {
      // Score based on time remaining (faster = more points)
      const timeBonus = Math.floor(this.timeLeft / 3);
      const points = 100 + timeBonus;
      this.score += points;

      sounds.play('correct');
      this.showFeedback(`✅ Correct! +${points} points`, 'success');
    } else {
      sounds.play('wrong');
      this.showFeedback(`❌ Wrong! The answer was: ${q.answer}`, 'error');
    }

    setTimeout(() => {
      this.currentQuestion++;
      this.showQuestion();
    }, 2000);
  }

  handleTimeout() {
    if (!this.gameActive) return;

    clearInterval(this.timer);
    clearInterval(this.tickInterval);

    const q = this.questions[this.currentQuestion];

    sounds.play('timeout');
    this.showFeedback(`⏰ Time's up! The answer was: ${q.answer}`, 'warning');

    setTimeout(() => {
      this.currentQuestion++;
      this.showQuestion();
    }, 2000);
  }

  showFeedback(message, type) {
    const feedback = document.createElement('div');
    feedback.style.cssText = `
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      background: var(--bg-surface);
      border: 2px solid var(--${type === 'success' ? 'success' : type === 'error' ? 'danger' : 'warning'});
      padding: 20px 40px;
      border-radius: var(--r-xl);
      font-size: 18px;
      font-weight: bold;
      z-index: 1000;
      animation: fadeIn 0.3s ease;
    `;
    feedback.textContent = message;
    document.body.appendChild(feedback);

    setTimeout(() => {
      feedback.remove();
    }, 1800);
  }

  endGame() {
    this.gameActive = false;
    clearInterval(this.timer);
    clearInterval(this.tickInterval);

    const maxScore = this.totalQuestions * 110; // Max possible with time bonus
    const percentage = Math.round((this.score / maxScore) * 100);

    if (percentage >= 70) {
      sounds.play('victory');
    } else {
      sounds.play('gameover');
    }

    this.container.innerHTML = `
      <div style="text-align: center; padding: 40px 20px;">
        <div style="font-size: 64px; margin-bottom: 20px;">
          ${percentage >= 70 ? '🏆' : percentage >= 50 ? '👍' : '💪'}
        </div>
        <h2 style="margin-bottom: 10px;">Quiz Complete!</h2>
        <div style="font-size: 24px; color: var(--accent); margin-bottom: 20px;">
          Score: ${this.score}/${maxScore}
        </div>
        <div style="font-size: 18px; color: var(--text-muted); margin-bottom: 30px;">
          ${percentage}% correct
        </div>
        <div style="font-size: 16px; margin-bottom: 30px;">
          ${percentage >= 90 ? '🌟 Emoji Master!' :
            percentage >= 70 ? '🎯 Great job!' :
            percentage >= 50 ? '👍 Good effort!' :
            '💪 Keep practicing!'}
        </div>
        <button id="play-again-btn" style="
          padding: 15px 40px;
          background: var(--accent);
          border: none;
          border-radius: var(--r-lg);
          font-size: 18px;
          cursor: pointer;
        ">Play Again</button>
      </div>
    `;

    this.container.querySelector('#play-again-btn').addEventListener('click', () => {
      sounds.play('click');
      this.start();
    });

    this.onComplete({
      score: this.score,
      maxScore: maxScore,
      percentage: percentage,
      gameType: 'emoji_quiz'
    });
  }
}

export default EmojiQuizGame;
export { EmojiQuizGame };
