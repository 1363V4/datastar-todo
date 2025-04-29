from quart import Quart, session, render_template, request
from datastar_py.sse import ServerSentEventGenerator as SSE
from tinydb import TinyDB
from faker import Faker
import uuid


# CONFIG

app = Quart(__name__)
app.secret_key = 'a_secret_key'

db = TinyDB("data.json", sort_keys=True, indent=2)
todos = db.table('todos')

fake = Faker()

# TODO

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

# APP STUFF

@app.before_request
async def before_request():
    if not session.get('user_id'):
        user_id = fake.name()
        session['user_id'] = user_id
    if not session.get('db_id'):
        db_id = todos.insert({'name': session['user_id'], 'actions':[{'type':'add','id':uuid.uuid4().hex,'content':'feed the cat'}]})
        session['db_id'] = db_id
    if not session.get('history'):
        session['history'] = 0

@app.route('/')
async def index():
    return await render_template('index.html')

@app.route('/todo')
async def todo():
    db_id = session['db_id']
    doc = todos.get(doc_id=db_id)
    hist = session['history']
    actions = doc['actions'][:-hist] if hist else doc['actions']
    tasks = await cqrs_remake(actions)
    html = """
<main id="main" class="gc">
  <div id="todo">
    <div id="todo-head" class="gt l">
        <span data-on-click="@get('/back')" class="button material-icons">arrow_circle_left</span>
        <span data-on-click="@get('/forward')" class="button material-icons">arrow_circle_right</span>
        the things we do for love
    </div>
    <div id="tasks">
"""
    for n, (task_id, task) in enumerate(tasks.items()):
        html += f"""
        <div id="task-{task_id}" class="task" data-signals-task{n}.editing="0">
            <div>
                {
                    f"<span data-on-click=\"@get('/uncheck/{task_id}')\" class=\"button material-icons\">check_circle</span>"
                    if task['checked']
                    else
                    f"<span data-on-click=\"@get('/check/{task_id}')\" class=\"button material-icons\">hide_source</span>"
                }
            </div>
            <div>        
                <div data-show="!$task{n}.editing">
                    {task['content']}
                    <span data-on-click="$task{n}.editing = 1" class="button material-icons">edit</span>
                </div>
                <form class="editor" data-show="$task{n}.editing" data-on-submit="@post('/edit/{task_id}', {{contentType: 'form'}})">
                    <input name="content" value="{task['content']}"/>
                    <button type="submit" class="button material-icons">done</button>
                </form>
            </div>
            <span data-on-click="@get('/delete/{task_id}')" class="button material-icons">delete</span>
        </div>
"""
    # html += '''<code data-text="ctx.signals.JSON()"></code>'''
    html += """
        <input placeholder="Add item" value="" data-bind-add data-on-blur="@post('/add')"/>
    </div>
  </div>
</main>
"""
    return SSE.merge_fragments(fragments=[html])

@app.post('/add')
async def add():
    signals = await request.json
    content = signals.get('add')
    if content:
        db_id = session['db_id']
        new_id = uuid.uuid4().hex
        todos.update(
            lambda d: d['actions'].append({'type':'add', 'id':new_id, 'content':content}), 
            doc_ids=[db_id]
        )
        session['history'] = 0
    return await todo()

@app.get('/delete/<task_id>')
async def delete(task_id):
    db_id = session['db_id']
    todos.update(
        lambda d: d['actions'].append({'type':'delete','id':task_id}), 
        doc_ids=[db_id]
    )
    session['history'] = 0
    return await todo()

@app.post('/edit/<task_id>')
async def edit(task_id):
    content = (await request.form).get('content')
    db_id = session['db_id']
    todos.update(
        lambda d: d['actions'].append({'type':'edit','id':task_id,'content':content}), 
        doc_ids=[db_id]
    )
    session['history'] = 0
    return await todo()

@app.get('/check/<task_id>')
async def check(task_id):
    db_id = session['db_id']
    todos.update(
        lambda d: d['actions'].append({'type':'check','id':task_id}), 
        doc_ids=[db_id]
    )
    session['history'] = 0
    return await todo()

@app.get('/uncheck/<task_id>')
async def uncheck(task_id):
    db_id = session['db_id']
    todos.update(
        lambda d: d['actions'].append({'type':'uncheck','id':task_id}), 
        doc_ids=[db_id]
    )
    session['history'] = 0
    return await todo()

@app.get('/back')
async def back():
    session['history'] += 1
    return await todo()

@app.get('/forward')
async def forward():
    session['history'] -= 1
    return await todo()

if __name__ == '__main__':
    app.run(debug=True)
