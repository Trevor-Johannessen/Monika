import os
from datetime import datetime
from agents import Agent, function_tool, ModelSettings, handoff
from removeReasoningItems import removeReasoningItems

class ScheduleTaskAgent(Agent):
    def __init__(self):
        super().__init__(
            name="schedule_agent",
            instructions="You are apart of a larger chatbot. You handle running tasks in the future. If you are told to run something in some time relative to now, get the current time first.",
            tools=[scheduleTask, listTask, removeTask, getDatetime],
            model_settings=ModelSettings(tool_choice="required"),
        )
        self.handoff = handoff(
            agent=self,
            tool_description_override="This should be called when action needs to be taken in the future. This agent is also able to remove scheduled prompts and list which prompts have already been scheduled.",
            input_filter=removeReasoningItems
        )
    
@function_tool
def getDatetime() -> str:
    """Gets the current date and time"""
    return datetime.now().strftime("%Y-%m-%d %H:%M")

@function_tool
def scheduleTask(time: str, task: str):
    """Schedules a task at a given date and time.
    
    Args:
        time: The date and time for the task to be executed using 'HH:MM AM/PM YYYY-MM-DD' syntax.
        task: A prompt describing what should be executed at the given time. This task will be fed into the AI and interpreted at time of execution.
    """
    try:
        # Remove quotes bc they're is enough escapes below and I don't want to do it anymore. 
        task = task.replace("\"","")
        task = task.replace("'","")
        data = os.system(f"""echo \"curl -X POST http://localhost:3333/prompt -H \\"Content-Type: application/json\\" -d \'{{\\"return_type\\": \\"text\\", \\"prompt\\": \\"{task}\\"}}'\" | at {time}""")
    except Exception as e:
        print(e)
    if data == 0:
        return "Success!"
    return "Could not schedule task."

@function_tool
def listTask() -> str:
    """Lists all currently queued one off tasks"""
    data = os.system("atq")
    return data.stdout

@function_tool
def removeTask(job_number: int):
    """Removes a job based off it's job number.

    Args:
        job_number: The id associated with the job to delete.
    """
    data = os.system(f"atrm {job_number}")
    if data.returncode == 0:
        return "Success!"
    return "Could not schedule task." 

@function_tool    
def scheduleReoccuring(minute: str, hour: str, day_of_month: str, month: str, day_of_week: str, task: str):
    pass

