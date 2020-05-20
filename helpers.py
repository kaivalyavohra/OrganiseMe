import sqlite3
from functools import wraps
from flask import session, redirect

def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/0.12/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/")
        return f(*args, **kwargs)
    return decorated_function


def match(studentEmails,coachEmails):
    superpowers = ["", "packingBag", "timeManagement",
                   "lockerUse", "filing", "hwDiary", "organizationTime"]
    students,dbvals = [],[]
    iteration = int(dbexecute("SELECT * from pairs ORDER BY iteration DESC;")[0]["iteration"])+1
    for email in studentEmails:
        students.extend(dbexecute("SELECT * FROM wagonwheel WHERE initOrFinal = 0 AND studentEmail = ?;",(email,)))
    for email in coachEmails:
        dbvals.extend(dbexecute("SELECT email,superpowerID FROM coach WHERE email = ?;",(email,)))

    coaches = []
    if len(students) > len(dbvals):
        return 0,0
    for coach in dbvals:
        temp = coach
        temp["superpowerID"] = superpowers[temp["superpowerID"]]
        coaches.append(temp)
    [print(coach['email'] + " : " + coach['superpowerID'])
     for coach in coaches]
    print("\n\n\n\n\n")
    studentdict = {}
    for student in students:
        studentemail = student["studentEmail"]
        temp = student
        del(temp["studentEmail"])
        del(temp["initOrFinal"])
        studentdict[studentemail] = sorted(temp.items(), key=lambda kv: kv[1])
    pairs = {}
    power = 0
    numofstudents = len(studentdict)
    while len(pairs) < numofstudents:
        studentsToDelete = []
        for stuemail, studict in studentdict.items():
            print(stuemail + " : " + studict[0][0] + " : " + studict[1][0])
            for coach in coaches:
                if studict[power][0] == coach["superpowerID"]:
                    pairs[stuemail] = coach["email"]
                    coachToDelete = coach
                    studentsToDelete.append(stuemail)

                    break
            try:
                coaches.remove(coachToDelete)
            except:
                print("error")
        for studentemail in studentsToDelete:
            del(studentdict[studentemail])

        power += 1

    return (pairs,iteration)

def dbexecute(query,arguments=()):
    conn = sqlite3.connect("data.sqlite")
    conn.row_factory = dict_factory
    c = conn.cursor()

    c.execute(query,arguments)
    response = c.fetchall()
    conn.commit()
    conn.close()
    return response

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d
