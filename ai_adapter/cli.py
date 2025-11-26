import asyncio, os
import typer
from rich import print
from dotenv import load_dotenv
from ai_adapter.core.router import Router
from ai_adapter.core.executor import Executor
from ai_adapter.core.memory import Memory
from ai_adapter.nlp.engines import make_engine
from ai_adapter.nlp.parser import SYSTEM_PROMPT


app = typer.Typer()


@app.command()
def chat():
    """Interactive chat → build & execute commands"""
    load_dotenv()
    engine = make_engine()
    intents_dir = os.path.join(os.path.dirname(__file__), 'intents')
    router = Router(intents_dir)
    execu = Executor(confirm=os.getenv('CONFIRMATION','ask')=='ask')
    mem = Memory()


    async def loop():
        while True:
            try:
                text = input("\n[You] ")
                if text.strip().lower() in {"quit","exit"}: break
                mem.add(text)
                data = await engine.parse(text, SYSTEM_PROMPT)
                intent = data.get('intent')
                params = data.get('params', {})
                spec = router.get(intent)
                cmds = execu.build(spec, params)
                code = execu.run(cmds)
                print(f"[green]Done. Exit code: {code}[/green]")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[red]Error:[/red] {e}")
    asyncio.run(loop())

def main():
    chat()

if __name__ == '__main__':
    main()