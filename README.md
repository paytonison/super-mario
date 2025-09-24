# AI-Powered Super Mario Experiment

This repository contains a fascinating experiment in artificial intelligence gaming: an AI agent that learns to play a Mario-style platformer using OpenAI's GPT models. The project demonstrates how large language models can be used for real-time game decision-making and provides multiple implementations for comparison.

![Mario Game Screenshot](https://github.com/user-attachments/assets/0e6cfaff-ff59-4acd-898d-e937c8f55a89)

## 🎮 What This Experiment Does

The AI agent receives real-time game state information and makes decisions about how Mario should move, jump, and navigate through the level. Rather than using traditional reinforcement learning or game trees, this experiment uses natural language prompts to describe the game state to GPT models, which then respond with appropriate actions.

### Key Features

- **Real-time AI Decision Making**: The AI processes game state every ~250ms and outputs movement commands
- **Multiple Implementations**: Web-based version, standalone Pygame version, and two different server architectures
- **Fallback Strategy**: Includes heuristic-based fallback when AI is unavailable
- **Interactive Control**: Players can toggle between AI and manual control
- **Visual Feedback**: Real-time display of AI decisions and game state

## 🏗 Architecture Overview

The experiment consists of several components that work together:

### 1. Web-Based Game (`mario/`)
- **Frontend**: HTML5 Canvas game (`public/game.js`, `public/index.html`)
- **Backend**: Express.js server (`server.js`) or Flask server (`server.py`)
- **AI Integration**: HTTP API calls to get AI decisions

### 2. Standalone Pygame Version (`mario/v0/`)
- **File**: `luigi_you_dumbass.py`
- **Purpose**: Direct integration with OpenAI API without server layer
- **Features**: Pygame-based rendering with built-in AI player

### 3. Server Implementations
Two different server approaches for AI decision-making:

#### Node.js Server (`server.js`)
- Uses OpenAI Chat Completions API
- Fast, lightweight implementation
- JSON-forced responses for reliability

#### Python Flask Server (`server.py`)
- Uses OpenAI Assistants API
- More sophisticated state management
- Thread-based conversation handling

## 🚀 Getting Started

### Prerequisites

1. **Node.js** (v18.17 or higher)
2. **Python** (for Pygame version)
3. **OpenAI API Key** (optional - works with heuristic fallback)

### Setup Instructions

1. **Clone the repository**:
   ```bash
   git clone https://github.com/paytonison/super-mario.git
   cd super-mario
   ```

2. **Install dependencies**:
   ```bash
   cd mario
   npm install
   ```

3. **Configure OpenAI API** (optional):
   ```bash
   # Create .env file
   echo "OPENAI_API_KEY=your_api_key_here" > .env
   ```

4. **Start the server**:
   ```bash
   # Option 1: Node.js server (recommended)
   npm start
   
   # Option 2: Python Flask server
   python server.py
   ```

5. **Open your browser**:
   Navigate to `http://localhost:3000`

### Running the Pygame Version

For the standalone Pygame implementation:

```bash
cd mario/v0
pip install -r requirements.txt
export OPENAI_API_KEY=your_api_key_here
python luigi_you_dumbass.py
```

## 🎯 How to Play

### Web Version Controls
- **Arrow Keys**: Manual control of Mario
- **A Key**: Toggle AI on/off
- **R Key**: Reset the game

### Game Mechanics
- **Objective**: Reach the flag at the end of the level
- **Obstacles**: Platforms, gaps, and enemies
- **Physics**: Gravity, momentum, and collision detection

## 🧠 How the AI Works

### Game State Processing

The AI receives a structured representation of the game world:

```javascript
{
  "player": {
    "x": 123,           // Player position
    "y": 456,
    "vx": 5,            // Velocity
    "vy": -2,
    "onGround": true    // Physics state
  },
  "nearGrid": [         // 5x9 grid around player
    [0,1,0,0,0,0,0,0,0], // Row 0 = ground level
    [0,0,0,0,0,0,0,0,0], // Row 1 = one tile up  
    // ... rows 2-4
  ],
  "goal": { "x": 3840 } // Target position
}
```

### Decision Making Process

1. **State Analysis**: AI analyzes the grid for obstacles, gaps, and enemies
2. **Strategic Planning**: Determines optimal path toward the goal
3. **Action Selection**: Chooses from available actions:
   - `idle` - No movement
   - `left` / `right` - Horizontal movement
   - `jump` - Vertical jump
   - `left_jump` / `right_jump` - Combined movements

### AI Prompting Strategy

The system uses carefully crafted prompts that:
- Describe the game mechanics clearly
- Provide structured state information
- Request specific JSON-formatted responses
- Include fallback strategies for edge cases

Example prompt excerpt:
```
You are a game-playing agent for a 2D platformer like Mario.
Output ONLY strict JSON: {"action":"<action_name>"}

Policy:
- Move right toward the goal
- If obstacle ahead or gap detected, use right_jump
- If airborne, keep moving right without additional jumps
```

### Fallback Heuristics

When the AI is unavailable, the system uses a simple heuristic:
- Always move right toward the goal
- Jump when obstacles or gaps are detected
- Avoid jumping while airborne

## 📊 Performance and Observations

### AI Behavior Patterns

The AI demonstrates several interesting behaviors:
- **Obstacle Avoidance**: Successfully identifies and jumps over barriers
- **Gap Navigation**: Detects missing floor tiles and responds appropriately  
- **Goal-Oriented Movement**: Maintains forward progress toward the objective
- **Physics Awareness**: Respects game physics (doesn't jump while airborne)

### Response Times
- **Node.js Server**: ~100-300ms response time
- **Python Server**: ~200-500ms response time
- **Pygame Direct**: ~250ms (configurable interval)

### Success Rate
Without specific training, the AI achieves reasonable performance through:
- Clear state representation
- Well-defined action spaces
- Strategic prompting
- Robust fallback mechanisms

## 🛠 Technical Details

### Dependencies

#### Node.js (Web Version)
```json
{
  "express": "^4.19.2",
  "cors": "^2.8.5", 
  "dotenv": "^16.6.1",
  "openai": "^4.104.0"
}
```

#### Python (Pygame Version)
- `pygame` - Game engine and rendering
- `openai` - AI API integration
- Standard library modules

### API Endpoints

#### `POST /agent/act`
Request AI decision for current game state.

**Request**:
```json
{
  "state": {
    "player": {...},
    "nearGrid": [...],
    "goal": {...}
  }
}
```

**Response**:
```json
{
  "action": "right_jump"
}
```

#### `GET /healthz`
Check server and AI configuration status.

**Response**:
```json
{
  "ok": true,
  "openaiConfigured": true,
  "model": "gpt-4o-mini"
}
```

### Configuration Options

#### Environment Variables
- `OPENAI_API_KEY` - Your OpenAI API key
- `PORT` - Server port (default: 3000)
- `OPENAI_ASSISTANT_ID` - For Python server (optional)
- `OPENAI_AGENT_MODEL` - AI model to use (default: gpt-4o-mini)

#### Game Parameters
- `FPS` - Game framerate (60)
- `TILE` - Tile size in pixels (32)
- `GRAVITY` - Physics gravity constant
- `JUMP_VY` - Jump velocity
- `MAX_SPEED_X` - Maximum horizontal speed

## 🚧 Experiment Insights

### What Works Well
- **Structured State Representation**: Clear grid-based world description
- **Simple Action Space**: Limited, well-defined movement options
- **Robust Fallbacks**: System continues functioning without AI
- **Real-time Performance**: Fast enough for interactive gameplay

### Challenges and Limitations
- **API Latency**: Network calls can introduce lag
- **Context Limitations**: AI doesn't maintain memory between decisions
- **Complexity Scaling**: More complex levels might challenge the approach
- **Cost Considerations**: API calls for every decision can be expensive

### Future Improvements
- **Memory Integration**: Add conversation history for better context
- **Multi-step Planning**: Enable longer-term strategic thinking
- **Learning Integration**: Combine with reinforcement learning approaches
- **Performance Optimization**: Reduce API call frequency
- **Advanced Prompting**: Experiment with few-shot learning examples

## 🤝 Contributing

This is an experimental project exploring AI gaming applications. Feel free to:
- Try different AI models or parameters
- Experiment with alternative prompting strategies
- Add new game mechanics or levels
- Optimize performance and response times
- Explore different AI architectures

## 📝 License

This project is for educational and experimental purposes. Please ensure you comply with OpenAI's usage policies when using their API.

## 🙏 Acknowledgments

This experiment demonstrates the creative potential of applying large language models to interactive gaming scenarios, pushing the boundaries of what's possible with prompt-based AI decision making.
