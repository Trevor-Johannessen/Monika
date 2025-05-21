"""
This script was written by Somesh on github for removing reasoning context from a history.
I've only made minor changes to the syntax.

Somesh: https://github.com/someshfengde
Comment: https://github.com/openai/openai-agents-python/issues/569#issuecomment-2862239227

"""
from agents import handoff
from agents.handoffs import HandoffInputData

def removeReasoningItems(handoff_input_data: HandoffInputData) -> HandoffInputData:
    """Filters out all reasoning items from the handoff data."""
    history = handoff_input_data.input_history
    
    # Filter out reasoning items from new_items
    filtered_new_items = tuple(item for item in handoff_input_data.new_items 
                              if getattr(item, 'type', None) != 'reasoning_item')
    
    # Filter out reasoning items from pre_handoff_items
    filtered_pre_handoff_items = tuple(item for item in handoff_input_data.pre_handoff_items 
                                      if getattr(item, 'type', None) != 'reasoning_item')

    return HandoffInputData(
        input_history=history,
        pre_handoff_items=filtered_pre_handoff_items,
        new_items=filtered_new_items,
    )
