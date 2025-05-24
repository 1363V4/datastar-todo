# Datastar Todo with CQRS Event Sourcing & Quart

A **Todo List** application built with **Datastar** and **Quart**, demonstrating the power of **CQRS (Command Query Responsibility Segregation) event sourcing** with reactive web interfaces. This project showcases how Datastar's Server-Sent Events (SSE) architecture enables seamless state management through immutable event streams.

## Overview

This project implements event sourcing where every user action becomes an immutable event in an append-only log. The current state is derived by replaying these events through a pure function, enabling powerful features like undo/redo, audit trails, and deterministic state reconstruction.

## Project Structure

```
datastar-todo/
├── main.py              # Quart application with CQRS architecture
├── templates/
│   └── index.html       # Datastar-powered reactive frontend
├── static/
│   └── css/
│       └── main.css     # Modern CSS with animations
├── datastar_py/         # Custom Datastar SSE utilities
│   ├── sse.py           # Server-Sent Events generator
│   └── consts.py        # Datastar event type constants
├── data.json            # TinyDB event store
└── pyproject.toml       # Python dependencies
```

## Technology Stack

- **Backend**: Quart (async Flask) with TinyDB for event persistence
- **Frontend**: Datastar for reactive UI updates via SSE
- **Architecture**: CQRS Event Sourcing with immutable event streams
- **State Management**: Pure functional state reconstruction from events
- **Communication**: Server-Sent Events for real-time UI synchronization

## CQRS Event Sourcing Architecture

### Core Principles

1. **Commands**: User actions that generate events (add, edit, delete, check)
2. **Events**: Immutable facts about what happened
3. **Queries**: State reconstruction from event history
4. **Separation**: Clear distinction between writes (commands) and reads (queries)

### Event Store Structure

Every user action creates an event in the append-only log:

```python
# Event examples stored in data.json
{
  "type": "add",
  "id": "uuid",
  "content": "Buy groceries"
}
{
  "type": "edit",
  "id": "uuid",
  "content": "Buy organic groceries"
}
{
  "type": "check",
  "id": "uuid"
}
{
  "type": "delete",
  "id": "uuid"
}
```

### State Reconstruction Function

The heart of the CQRS pattern - a pure function that rebuilds state from events:

```python
async def cqrs_remake(actions):
    tasks = {}
    for action in actions:
        match action:
            case {'type':'add', 'id':task_id, 'content':content}:
                tasks[task_id] = {'content':content, 'checked': False}
            case {'type':'delete', 'id':task_id}:
                tasks.pop(task_id, None)
            case {'type':'edit', 'id':task_id, 'content':content} if task_id in tasks:
                tasks[task_id]['content'] = content
            case {'type':'check', 'id':task_id} if task_id in tasks:
                tasks[task_id]['checked'] = True
            case {'type':'uncheck', 'id':task_id} if task_id in tasks:
                tasks[task_id]['checked'] = False
            case _:
                pass
    return tasks
```

**Key Features**:

- **Pure Function**: No side effects, deterministic output
- **Pattern Matching**: Modern Python syntax for event handling
- **Immutable**: Original events never change
- **Defensive**: Guards against invalid state transitions
- **Auditable**: Every state change has a traceable event

### Time Travel Implementation

The application includes **undo & redo** through history navigation:

```python
@app.get('/back')
async def back():
    session['history'] += 1  # Exclude more recent events
    return await todo()

@app.get('/forward')
async def forward():
    session['history'] -= 1  # Include more recent events
    return await todo()
```

**State at Any Point in Time**:

```python
@app.route('/todo')
async def todo():
    db_id = session['db_id']
    doc = todos.get(doc_id=db_id)
    hist = session['history']

    # Slice event stream to specific point in time
    actions = doc['actions'][:-hist] if hist else doc['actions']

    # Reconstruct state at that moment
    tasks = await cqrs_remake(actions)
```

**Benefits**:

- **Debug Complex Issues**: See exactly when things went wrong
- **Perfect Audit Trail**: Know who did what when
- **Recovery**: Restore to any previous state
- **Testing**: Verify state at specific event sequences

## Datastar Integration & Features

### 1. Server-Sent Events for Reactive Updates

Every user action triggers an SSE response that updates the UI:

```python
@app.post('/add')
async def add():
    signals = await request.json
    content = signals.get('add')
    if content:
        # COMMAND: Append event to store
        new_id = uuid.uuid4().hex
        todos.update(
            lambda d: d['actions'].append({
                'type':'add',
                'id':new_id,
                'content':content
            }),
            doc_ids=[db_id]
        )
        session['history'] = 0  # Reset to latest state

    # QUERY: Rebuild and return current state
    return await todo()
```

**SSE Response Pattern**:

```python
return SSE.merge_fragments(fragments=[html])
```

### 2. Dynamic Signal-Driven UI

Datastar signals control per-task editing state without explicit state management:

```html
<div id="task-{task_id}" class="task" data-signals-task{n}.editing="0">
  <div data-show="!$task{n}.editing">
    {task['content']}
    <span data-on-click="$task{n}.editing = 1" class="button">edit</span>
  </div>
  <form data-show="$task{n}.editing" data-on-submit="@post('/edit/{task_id}')">
    <input name="content" value="{task['content']}" />
    <button type="submit" class="button">done</button>
  </form>
</div>
```

**Key Features**:

- **Per-Task Signals**: `$task{n}.editing` creates isolated editing state
- **Conditional Rendering**: `data-show` toggles between view/edit modes
- **No JavaScript**: Pure declarative UI logic
- **Reactive Updates**: Changes propagate instantly via SSE

### 3. Seamless Form Handling

Multiple input methods with automatic binding:

```html
<!-- Two-way binding for new tasks -->
<input
  placeholder="Add item"
  value=""
  data-bind-add
  data-on-blur="@post('/add')"
/>

<!-- Form-based editing -->
<form data-on-submit="@post('/edit/{task_id}', {{contentType: 'form'}})">
  <input name="content" value="{task['content']}" />
  <button type="submit">done</button>
</form>
```

**Integration Points**:

- **`data-bind-add`**: Automatic signal binding for new task input
- **`data-on-blur`**: Submit on focus loss for better UX

### 4. RESTful Action Commands

```python
@app.get('/delete/<task_id>')
async def delete(task_id):
    # COMMAND: Append delete event
    todos.update(
        lambda d: d['actions'].append({'type':'delete','id':task_id}),
        doc_ids=[db_id]
    )
    return await todo()  # QUERY: Return updated state

@app.get('/check/<task_id>')
async def check(task_id):
    # COMMAND: Append check event
    todos.update(
        lambda d: d['actions'].append({'type':'check','id':task_id}),
        doc_ids=[db_id]
    )
    return await todo()  # QUERY: Return updated state
```

**Frontend Integration**:

```html
<span data-on-click="@get('/check/{task_id}')" class="button">✓</span>
<span data-on-click="@get('/delete/{task_id}')" class="button">🗑</span>
```

**Architecture Benefits**:

- **Consistent Pattern**: All actions follow command → event → query flow
- **Stateless Endpoints**: Each request is independent
- **SSE Responses**: Uniform UI update mechanism

### 5. Automatic Session Management

Seamless user experience with automatic initialization:

```python
@app.before_request
async def before_request():
    if not session.get('user_id'):
        user_id = fake.name()  # Generate random user
        session['user_id'] = user_id

    if not session.get('db_id'):
        # Initialize with welcome task
        db_id = todos.insert({
            'name': session['user_id'],
            'actions':[{
                'type':'add',
                'id':uuid.uuid4().hex,
                'content':'feed the cat'
            }]
        })
        session['db_id'] = db_id

    if not session.get('history'):
        session['history'] = 0  # Start at latest state
```

**Benefits**:

- **Zero Setup**: Users immediately see a working todo list
- **Isolated State**: Each session gets independent event stream

## CQRS Benefits Demonstrated

### 1. Perfect Audit Trail

Every change is traceable:

```json
{
  "actions": [
    { "type": "add", "id": "abc", "content": "Buy milk", "timestamp": "..." },
    {
      "type": "edit",
      "id": "abc",
      "content": "Buy organic milk",
      "timestamp": "..."
    },
    { "type": "check", "id": "abc", "timestamp": "..." },
    { "type": "delete", "id": "abc", "timestamp": "..." }
  ]
}
```

### 2. Undo & Redo

Navigate through historical states:

- **Back Button**: `@get('/back')` - Move backward in time
- **Forward Button**: `@get('/forward')` - Move forward in time
- **State Reconstruction**: View exact state at any point

### 3. Deterministic State

The same events always produce the same state:

```python
# Always deterministic
final_state = cqrs_remake([
    {'type':'add', 'id':'1', 'content':'task'},
    {'type':'check', 'id':'1'},
    {'type':'edit', 'id':'1', 'content':'updated task'}
])
```

## Running the Application

### Prerequisites

- Python 3.12+
- uv package manager

### Setup

1. **Install dependencies**:

```bash
uv sync
```

2. **Run the application**:

```bash
uv run main.py
```

3. **Use the app**: Open `http://localhost:5000` in your browser

### Features to Try

- **Add Tasks**: Type in the input field and blur to add
- **Edit Tasks**: Click edit icon, modify, and submit
- **Check/Uncheck**: Toggle task completion status
- **Delete Tasks**: Remove tasks permanently
- **Time Travel**: Use back/forward buttons to navigate history
- **Persistence**: Refresh page - your todo list persists

## Key Datastar Patterns Demonstrated

### SSE-Driven State Updates

```python
return SSE.merge_fragments(fragments=[html])
```

### Signal-Based UI Logic

```html
data-signals-task{n}.editing="0" data-show="!$task{n}.editing"
```

### Declarative Action Binding

```html
<span data-on-click="@get('/delete/{task_id}')" class="button material-icons">
  delete
</span>
```

### Automatic Form Integration

```html
<input
  placeholder="Add item"
  value=""
  data-bind-add
  data-on-blur="@post('/add')"
/>
```

### Declarative show/hide

```html
<div data-show="!$task{n}.editing">
  {task['content']}
  <span data-on-click="$task{n}.editing = 1" class="button material-icons">
    edit
  </span>
</div>
```
