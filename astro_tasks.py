import yaml

class Task:
    def __init__(self, action, **kwargs):
        self.action = action
        self.params = kwargs

    def __repr__(self):
        return f"{self.action!r}: {self.params!r}"

def parse_tasks_yaml(yaml_content):
    data = yaml.safe_load(yaml_content)
    tasks = []
    for item in data.get('tasks', []):
        if isinstance(item, dict):
            action = item.get('action')
            params = {k: v for k, v in item.items() if k != 'action'}
            tasks.append(Task(action, **params))
    return tasks

def parse_tasks_yaml_file(file_path):
    with open(file_path, 'r') as f:
        yaml_content = f.read()
    return parse_tasks_yaml(yaml_content)

# Example usage:
if __name__ == "__main__":
    yaml_content = """
tasks:
    - action: goto
      object: alberio
    - action: start_phd
    - action: take_exposures
      count: 50
      duration_sec: 180
    - action: stop_phd
    - action: goto
      object: M31
    - action: start_phd
    - action: take_exposures
      count: 20
      duration_sec: 90
    - action: stop_phd
    - action: park_mount
"""
    tasks = parse_tasks_yaml_file(r"C:\images\20241103\C23\Light\tasks.txt")
    for task in tasks:
        print(task)