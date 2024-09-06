import itertools
import openai
import os

# Set OpenAI API key
os.environ['OPENAI_API_KEY'] = 
client = openai.OpenAI()

# Function to generate all possible timetables
def generate_all_possible_timetables(details, openai_constraints):
    print("Generating all possible timetables...")

    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    periods_per_day = details["periods_per_day"]
    subjects = list(details["school_subjects"].keys())
    
    all_timetables = []
    subject_combinations = itertools.product(subjects, repeat=periods_per_day)
    
    for day_combination in subject_combinations:
        timetable = {day: [] for day in days_of_week}
        for day in days_of_week:
            day_schedule = []
            for period_idx, subject in enumerate(day_combination):
                teacher = get_valid_teacher(subject, details)
                room = get_valid_room(details)
                day_schedule.append({
                    "period": period_idx + 1,
                    "subject": subject,
                    "teacher": teacher,
                    "room": room
                })
            timetable[day] = day_schedule

        # Validate the generated timetable, checking both hardcoded and OpenAI-generated constraints
        if validate_single_timetable(timetable, details, openai_constraints):
            print('Valid timetable generated.')
            all_timetables.append(timetable)
            print(timetable)
    
    print(f"Generated {len(all_timetables)} valid timetables.")
    return all_timetables

# Helper function to get a valid teacher for the subject
def get_valid_teacher(subject, details):
    for teacher, info in details["teachers"].items():
        if subject in info["subjects"]:
            return teacher
    return None

# Helper function to get a valid room
def get_valid_room(details):
    return details["rooms"][0]

# Hardcoded constraints validation
def constraint_min_hours_per_subject(timetable, details):
    subject_hours = {subject: 0 for subject in details["school_subjects"]}
    for day, schedule in timetable.items():
        for period in schedule:
            subject_hours[period["subject"]] += 1
    for subject, min_hours in details["school_subjects"].items():
        if subject_hours[subject] < min_hours["min_hours"]:
            return False
    return True

def constraint_max_hours_per_teacher(timetable, details):
    teacher_hours = {teacher: 0 for teacher in details["teachers"]}
    for day, schedule in timetable.items():
        for period in schedule:
            teacher_hours[period["teacher"]] += 1
    for teacher, info in details["teachers"].items():
        if teacher_hours[teacher] > info["max_hours"]:
            return False
    return True

def constraint_diverse_subjects_per_day(timetable):
    for day, schedule in timetable.items():
        subjects_taught = {period["subject"] for period in schedule}
        if len(subjects_taught) < len(schedule) // 3:
            return False
    return True

# Function to generate an empty timetable skeleton (for prompt use)
def generate_empty_timetable_skeleton(details):
    periods_per_day = details["periods_per_day"]
    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    timetable = {day: [] for day in days_of_week}

    for day in days_of_week:
        for period in range(1, periods_per_day + 1):
            timetable[day].append({
                "period": period,
                "subject": None,
                "teacher": None,
                "room": None
            })

    print("Empty timetable skeleton generated.")
    return timetable

# Function to generate and execute if-statements for the constraints using OpenAI
def generate_if_statements(constraints, details, timetable_skeleton):
    print("Generating if-statements for constraints...")
    teacher_details_str = "\n".join([f"{teacher}: {', '.join(info['subjects'])}, max {info['max_hours']} hours per week"
                                     for teacher, info in details['teachers'].items()])
    subjects_taught_str = ", ".join(details['school_subjects'].keys())
    rooms_str = ", ".join(details['rooms'])

    timetable_str = "{\n"
    for day, schedule in timetable_skeleton.items():
        timetable_str += f'    "{day}": [\n'
        for entry in schedule:
            timetable_str += f'        {{"period": {entry["period"]}, "subject": {entry["subject"]}, "teacher": {entry["teacher"]}, "room": {entry["room"]}}},\n'
        timetable_str += "    ],\n"
    timetable_str += "}"

    if_statements = []

    for idx, constraint in enumerate(constraints):
        print(f"Generating if-statement for constraint {idx + 1}: {constraint}")
        prompt = f"""
        You are a very helpful assistant, that can convert raw text to if-statements in Python!

        Given that the teachers' names, the subjects they teach, and the maximum hours each teacher teaches per week are as follows:
        {teacher_details_str}

        The number of periods per day is {details['periods_per_day']}.
        The subjects taught are {subjects_taught_str}
        The rooms available are {rooms_str}

        THE DATA STRUCTURE OF THE TIMETABLE IS AS FOLLOWS: THIS IS AN EXAMPLE
        timetable = {timetable_str}

        Additional constraints should be noted and converted to if-statements that return False if they are not fulfilled. If they are fulfilled, they should return True.

        For example,
        if a constraint is that: "Math must be taught in the first two periods"
        THE CORRESPONDING if-statement would be:

        def check_math_first_two_periods(timetable):
            for day, schedule in timetable.items():
                if schedule[0]["subject"] != "Math" or schedule[1]["subject"] != "Math":
                    return False
            return True

        ONLY GIVE ME THE IF STATEMENTS, AND RETURN FUNCTIONS AND NO EXTRA TEXT.

        Here is the constraint: "{constraint}"
        """

        # Use OpenAI to generate the Python code (constraint function)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"This is constraint {idx + 1}. Please name the function 'constraint{idx+1}'."}
            ]
        )

        # Capture the constraint function from the response
        if_statement = response.choices[0].message.content.strip("```").strip()
        if_statements.append(if_statement)
        print(f"Generated if-statement for constraint {idx + 1}: {if_statement}")

        # Execute the generated Python code string to define the function
        exec(if_statement, globals())

    print("If-statements generated and executed.")
    return if_statements

# Validate a single timetable with hardcoded and OpenAI constraints
def validate_single_timetable(timetable, details, openai_constraints=None):
    # Validate hardcoded constraints
    if not constraint_min_hours_per_subject(timetable, details):
        return False
    if not constraint_max_hours_per_teacher(timetable, details):
        return False
    if not constraint_diverse_subjects_per_day(timetable):
        return False
    
    # Validate OpenAI-generated constraints
    if openai_constraints:
        for idx, constraint_function in enumerate(openai_constraints):
            # #print(constraint_function)
            # if f'constraint{idx + 1}' in globals():
            #     print(f'')

            if not globals()[f'constraint{idx + 1}'](timetable): 
                #print(f"failed on constraint{idx + 1}")
                #print(timetable)
                return False
    print("all constraints ok!!! \n")
    return True

# Main function
def main():
    details = {
        'teachers': {
            'Alice': {'subjects': ['Math'], 'max_hours': 10}, 
            'Bob': {'subjects': ['Physics'], 'max_hours': 10}, 
            'Cindy': {'subjects': ['Biology', 'Chemistry'], 'max_hours': 10}, 
            'Dave': {'subjects': ['English'], 'max_hours': 10}, 
            'Ella': {'subjects': ['History', 'Geography'], 'max_hours': 10}, 
            'Frank': {'subjects': ['Computer Science'], 'max_hours': 10}
        },
        'periods_per_day': 9, 
        'school_subjects': {
            'Math': {'min_hours': 2}, 
            'Physics': {'min_hours': 2}, 
            'Biology': {'min_hours': 2}, 
            'Chemistry': {'min_hours': 2}, 
            'English': {'min_hours': 2}, 
            'History': {'min_hours': 2}, 
            'Geography': {'min_hours': 3}, 
            'Computer Science': {'min_hours': 3}
        }, 
        'rooms': ['101', '102', '103', '104', '105', '106', '107', '108', '109']
    }

    timetable_outline = generate_empty_timetable_skeleton(details)

    # OpenAI-based constraints
    constraints = ["Chemistry must always be taught in the second half of the day (periods 5-9).", "Math must be taught in the last period everyday.", "Computer science should be taught right before math ONLY on Tuesday. The rest of the days should be different", "Physics should be the second to last period everyday except Tuesday."]
    openai_constraints = generate_if_statements(constraints, details, timetable_outline)

    # Generate timetables and check against both hardcoded and OpenAI constraints
    valid_timetables = generate_all_possible_timetables(details, openai_constraints=openai_constraints)
    
    for idx, timetable in enumerate(valid_timetables):
        print(f"\nTimetable {idx + 1}:")
        for day, periods in timetable.items():
            print(f"\n{day}:")
            for period in periods:
                print(f"  Period {period['period']}: Subject: {period['subject']}, Teacher: {period['teacher']}, Room: {period['room']}")

# Run the main function
if __name__ == "__main__":
    main()
