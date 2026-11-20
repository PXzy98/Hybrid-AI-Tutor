# ruff: noqa: E501
"""Z22: held-out E6 sets for the course types (written blind: the recognizer rules were not read first).

Four sets of fictional student questions, each with identifiers (labelled spans) and clean technical or
course questions that must not be redacted (`keep` = terms that must survive):

    ece_holdout.jsonl       ECE (profile `ece`)
    cs_holdout.jsonl        computer science (profile `computer_science`), code snippets with secrets
    life_holdout.jsonl      life science (profile `life_science`)
    general_holdout.jsonl   any other course (profile `general`)

Every name, number, key and address is invented (keys carry FAKE/notreal markers, hosts use private ranges
or example domains). Same record format as ece_cases.jsonl.

    .venv\\Scripts\\python eval\\privacy-filter\\make_course_sets.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = "positive"
N = "negative"

# (text, [(type, span text)], [keep terms])
ECE = [
    ("Hi, I'm Priya Nambiar (student number 300517264) and my op-amp circuit saturates at 4.7 V. What is wrong with my feedback resistor?",
     [("PERSON", "Priya Nambiar"), ("STUDENT_ID", "300517264")], ["op-amp", "4.7 V"]),
    ("My TA Marcus Ellery said to email him at marcus.ellery@labmail-example.ca but I forgot what to write about the Bode plot.",
     [("PERSON", "Marcus Ellery"), ("EMAIL_ADDRESS", "marcus.ellery@labmail-example.ca")], ["Bode plot"]),
    ("The FPGA board in the lab answers to ssh pi@192.168.40.17 but the bitstream upload times out. Which port does JTAG use?",
     [("INTERNAL_ADDRESS", "192.168.40.17")], ["FPGA", "JTAG"]),
    ("Our group repo is https://github.com/tkowalski-lab3/pid-controller and the CI fails on the linting step. How do I read the log?",
     [("REPO_URL", "https://github.com/tkowalski-lab3/pid-controller")], ["CI"]),
    ("I committed this by accident: AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY. Do I need to rotate it before the demo?",
     [("SECRET", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")], ["rotate"]),
    ("Call me on 613-555-0147 if you can explain why my 555 timer oscillates at 1.2 kHz instead of 1 kHz.",
     [("PHONE_NUMBER", "613-555-0147")], ["555 timer", "1.2 kHz"]),
    ("The Raspberry Pi in the embedded lab is at 10.12.7.45:8080, and curl returns connection refused. Is the service bound to localhost only?",
     [("INTERNAL_ADDRESS", "10.12.7.45:8080")], ["curl", "localhost"]),
    ("Student 301288451 here: how many bits does a 12-bit ADC need to resolve 2.5 mV with a 5 V reference?",
     [("STUDENT_ID", "301288451")], ["12-bit ADC", "5 V"]),
    ("In my ROS node I set the token to xoxb-0000000000-FAKE1111111111-notrealnotrealnotreal and the Slack bot still does not post. Why?",
     [("SECRET", "xoxb-0000000000-FAKE1111111111-notrealnotrealnotreal")], ["ROS"]),
    ("Can you check my git remote? It says git@github.com:fatima-hadid-ece/stm32-uart-driver.git and push is denied.",
     [("REPO_URL", "git@github.com:fatima-hadid-ece/stm32-uart-driver.git")], ["push"]),
    ("My lab partner Jun-ho Baek and I disagree about the Nyquist rate for a 20 kHz signal. Who is right?",
     [("PERSON", "Jun-ho Baek")], ["Nyquist", "20 kHz"]),
    ("The oscilloscope in room B-204 is on the lab VLAN at 172.16.8.203. Why can't I reach the web interface from my laptop?",
     [("INTERNAL_ADDRESS", "172.16.8.203")], ["VLAN"]),
    ("Please send the grading rubric to olusegun.adeyemi@student-example.ca, and explain how the Smith chart maps a 50 ohm load.",
     [("EMAIL_ADDRESS", "olusegun.adeyemi@student-example.ca")], ["Smith chart", "50 ohm"]),
    ("export API_TOKEN=\"tok_FAKE_9d8c7b6a5f4e3d2c1b0a_notreal\" is in my .bashrc; does the MQTT client read it from there?",
     [("SECRET", "tok_FAKE_9d8c7b6a5f4e3d2c1b0a_notreal")], ["MQTT"]),
    ("I'm Elena Voskresenskaya, ID 300699127, and my Verilog testbench never finishes. Does $finish need a delay?",
     [("PERSON", "Elena Voskresenskaya"), ("STUDENT_ID", "300699127")], ["Verilog", "testbench"]),
    ("Our project is hosted at gitlab.com/ottawa-ece-team7/motor-driver and my teammate cannot clone it. Is it a permission problem?",
     [("REPO_URL", "gitlab.com/ottawa-ece-team7/motor-driver")], ["clone"]),
    ("The MAC address of the lab switch is 00:1A:2B:3C:4D:5E and I want to filter it in Wireshark. What filter expression do I use?",
     [("INTERNAL_ADDRESS", "00:1A:2B:3C:4D:5E")], ["Wireshark"]),
    ("My broker URL is mqtt://sensor_user:Rt7Fake!Pass@10.30.2.9:1883 and it fails with not authorised. What does return code 5 mean?",
     [("SECRET", "Rt7Fake!Pass"), ("INTERNAL_ADDRESS", "10.30.2.9:1883")], ["return code 5"]),
    ("Dr. Haruka Sato's office hours are on Thursday, right? I want to ask about the Laplace transform of a unit step. My cell is (343) 555-0119.",
     [("PERSON", "Haruka Sato"), ("PHONE_NUMBER", "(343) 555-0119")], ["Laplace transform"]),
    ("Header looks like Authorization: Bearer eyJhbGciOiJub25lIn0.eyJ1c2VyIjoiZmFrZSJ9.FAKEsig0123456789 and the API gives 403. How is a Bearer token checked?",
     [("SECRET", "eyJhbGciOiJub25lIn0.eyJ1c2VyIjoiZmFrZSJ9.FAKEsig0123456789")], ["Bearer", "403"]),
    ("Hey it's Tomasz (tomasz.wrona@mail-example.org). Why does my RLC circuit ring when R is only 10 ohm?",
     [("EMAIL_ADDRESS", "tomasz.wrona@mail-example.org")], ["RLC", "10 ohm"]),
    ("The test server is at http://192.168.1.88:5000/api/v2/status and returns an empty JSON. How do I debug a Flask route?",
     [("INTERNAL_ADDRESS", "192.168.1.88:5000")], ["Flask", "JSON"]),
    ("My teammate Aisha Rahman pushed to https://bitbucket.org/arahman-ece/radio-firmware and now I have merge conflicts in main.c. How do I resolve them?",
     [("PERSON", "Aisha Rahman"), ("REPO_URL", "https://bitbucket.org/arahman-ece/radio-firmware")], ["merge conflicts"]),
    ("password = 'Winter#Lab2026x' appears in my config.ini. Is it OK to keep it if the repo is private?",
     [("SECRET", "Winter#Lab2026x")], ["config.ini"]),
    ("Student ID 300804553, why is the Fourier series of a square wave only odd harmonics?",
     [("STUDENT_ID", "300804553")], ["Fourier series", "odd harmonics"]),
    # negatives
    ("A 4.7k resistor in series with a 100 nF capacitor gives what cutoff frequency?", [], ["4.7k", "100 nF"]),
    ("Which firmware version is stable: 1.2.3.4 or 2.0.1.15? The release notes only list the build 10.4.2.", [], ["1.2.3.4", "2.0.1.15"]),
    ("Can I replace an LM358 with a TL072 in my active filter? Both are dual op-amps.", [], ["LM358", "TL072"]),
    ("The datasheet of the ATmega328P lists 32 KB flash and 2 KB SRAM. How is the memory map organised?", [], ["ATmega328P"]),
    ("What is the subnet mask for 192.168.0.0/24 and how many hosts fit in it?", [], ["192.168.0.0/24"]),
    ("Why does the voltage across the inductor lead the current by 90 degrees in AC steady state?", [], ["90 degrees"]),
    ("The transistor 2N3904 has a beta of about 100. How do I bias it at Ic = 2 mA?", [], ["2N3904", "2 mA"]),
    ("Explain the difference between a Mealy and a Moore machine with a traffic light example.", [], ["Mealy", "Moore"]),
    ("What does the error 'Permission denied (publickey)' mean when I use git over SSH?", [], ["publickey"]),
    ("In the lab manual, Figure 3.2 shows a 1:10 probe. Why do I need to compensate it with the 1 kHz square wave?", [], ["1:10 probe", "1 kHz"]),
    ("How do I compute the Thevenin equivalent seen by a 1 kohm load from a 12 V source and a 220 ohm resistor?", [], ["Thevenin", "1 kohm"]),
    ("Python 3.11.4 raises ModuleNotFoundError for numpy in my virtualenv. How do I install it?", [], ["3.11.4", "numpy"]),
    ("Is the I2C address 0x48 of the TMP102 sensor fixed, or can I change it with the ADD0 pin?", [], ["0x48", "TMP102"]),
    ("What is the key idea of the Kalman filter and why does the gain K converge?", [], ["Kalman", "key"]),
    ("Our group chose the license MIT for the repo. Does that affect how the TA can grade our code?", [], ["MIT"]),
    ("My op-amp circuit has a gain of -10 with Rf = 100k and Rin = 10k. Is the output limited by a +/-15 V supply?", [], ["100k", "15 V"]),
]

CS = [
    ("My script has client = boto3.client('s3', aws_access_key_id='AKIAFAKE0000EXAMPLE1', aws_secret_access_key='fakeSecretKey+0000notreal/EXAMPLEEXAMPLE') and it returns 403. What am I missing?",
     [("SECRET", "AKIAFAKE0000EXAMPLE1"), ("SECRET", "fakeSecretKey+0000notreal/EXAMPLEEXAMPLE")], ["boto3", "403"]),
    ("Here is my code: conn = psycopg2.connect(host='10.20.4.12', user='cs_student', password='Hunter2-fake-pw') and it hangs. Is it a timeout?",
     [("INTERNAL_ADDRESS", "10.20.4.12"), ("SECRET", "Hunter2-fake-pw")], ["psycopg2"]),
    ("I'm Mei-Ling Chow (301155802). My recursion for Fibonacci blows the stack at n = 10000. How do I make it iterative?",
     [("PERSON", "Mei-Ling Chow"), ("STUDENT_ID", "301155802")], ["Fibonacci", "10000"]),
    ("git clone https://github.com/dkarlsson-cs/hash-table-lab.git works for me but my partner gets a 404. Why?",
     [("REPO_URL", "https://github.com/dkarlsson-cs/hash-table-lab.git")], ["404"]),
    ("const OPENAI_KEY = 'sk-fake-0000111122223333444455556666notreal'; // is this safe to leave in my React app?",
     [("SECRET", "sk-fake-0000111122223333444455556666notreal")], ["React"]),
    ("My .env has DATABASE_URL=postgres://admin:Fake_Pw_8812@db.lab-example.net:5432/shop and Django still cannot connect. What else should I check?",
     [("SECRET", "Fake_Pw_8812")], ["Django"]),
    ("Prof. Ingrid Solberg said the midterm covers red-black trees. Can you explain the rotation cases? You can write to me at wei.zhang@cs-example.ca.",
     [("PERSON", "Ingrid Solberg"), ("EMAIL_ADDRESS", "wei.zhang@cs-example.ca")], ["red-black trees"]),
    ("My web server listens on 192.168.100.23:3000 in the lab network, why can't my phone open it?",
     [("INTERNAL_ADDRESS", "192.168.100.23:3000")], ["web server"]),
    ("headers = {'Authorization': 'Bearer FAKEtoken0123456789abcdefnotreal'} gives 401 on every request. How do I debug requests?",
     [("SECRET", "FAKEtoken0123456789abcdefnotreal")], ["401", "requests"]),
    ("Why is bubble sort O(n^2)? My ID is 300912736 if you need it for the quiz.",
     [("STUDENT_ID", "300912736")], ["bubble sort", "O(n^2)"]),
    ("My fork is at github.com/sanjay-p-2026/6006-pset3 and the tests pass locally but fail in the autograder. Where do I look?",
     [("REPO_URL", "github.com/sanjay-p-2026/6006-pset3")], ["autograder"]),
    ("api_key = \"ghp_FAKE1234567890abcdefghijklmnopqrstuv\"; requests.get(url, headers={'X-Key': api_key}) -> how do I load it from an environment variable instead?",
     [("SECRET", "ghp_FAKE1234567890abcdefghijklmnopqrstuv")], ["environment variable"]),
    ("Hi, Olivia Brennan here, phone 416-555-0178. Can you explain Dijkstra's algorithm with a priority queue?",
     [("PERSON", "Olivia Brennan"), ("PHONE_NUMBER", "416-555-0178")], ["Dijkstra", "priority queue"]),
    ("My MongoDB string is mongodb+srv://cs50user:Notreal-4411@cluster0.fake-example.mongodb.net/test and the connection times out. Is my IP whitelisted?",
     [("SECRET", "Notreal-4411")], ["MongoDB"]),
    ("The course VM is at 172.20.15.31 and ssh asks for a password that I never set. Where do I find it?",
     [("INTERNAL_ADDRESS", "172.20.15.31")], ["ssh"]),
    ("-----BEGIN RSA PRIVATE KEY-----\nMIIFAKEFAKEFAKEnotrealnotrealnotreal0000\n-----END RSA PRIVATE KEY-----\nIs it a problem that I pasted this key file into my GitHub repository?",
     [("SECRET", "MIIFAKEFAKEFAKEnotrealnotrealnotreal0000")], ["GitHub"]),
    # negatives
    ("What is the time complexity of binary search on a sorted array of 1,000,000 elements?", [], ["1,000,000"]),
    ("In my C code, int *p = malloc(10 * sizeof(int)); then p[10] = 5; why does valgrind complain?", [], ["valgrind", "malloc"]),
    ("Explain the difference between a mutex and a semaphore. Also why is the version 3.9.2 of Python mentioned in the syllabus?", [], ["mutex", "3.9.2"]),
    ("def hash_password(pw): return hashlib.sha256(pw.encode()).hexdigest() -- is SHA-256 enough for storing passwords?", [], ["SHA-256", "hashlib"]),
    ("How does a TCP three-way handshake differ from UDP? My notes say port 443 for HTTPS and 53 for DNS.", [], ["443", "DNS"]),
    ("Why does git say 'detached HEAD' after I checkout a1b2c3d? How do I go back to main?", [], ["a1b2c3d", "detached HEAD"]),
    ("What should the API key rotation policy look like in a real company? We only discuss it in theory in lecture 9.", [], ["API key rotation"]),
    ("for i in range(1, 11): print(i ** 2) prints 1 4 9 ... 100. How would I write it as a list comprehension?", [], ["list comprehension"]),
    ("Is 127.0.0.1 the same as localhost, and what is 0.0.0.0 used for when a server binds?", [], ["127.0.0.1", "0.0.0.0"]),
    ("In Java, how do I make a class immutable? Should the fields be private final?", [], ["immutable"]),
    ("SELECT name FROM students WHERE gpa > 3.5 ORDER BY name; returns an empty table, what is wrong with it?", [], ["SELECT", "3.5"]),
    ("Please explain why quicksort has worst case O(n^2) and how a random pivot or the median of 3 helps.", [], ["quicksort", "median of 3"]),
    ("How do I read an environment variable called SECRET_KEY in Flask without hardcoding the value?", [], ["SECRET_KEY"]),
    ("What does the HTTP status 418 mean and is it a real standard?", [], ["418"]),
]

LIFE = [
    ("I'm Camila Restrepo (student 300731986) and I don't understand why the Hardy-Weinberg equilibrium needs random mating. Can you explain?",
     [("PERSON", "Camila Restrepo"), ("STUDENT_ID", "300731986")], ["Hardy-Weinberg"]),
    ("My lab partner Kwame Asante forgot to label sample S-0042. How do I find the right PCR product on the gel?",
     [("PERSON", "Kwame Asante")], ["PCR", "gel"]),
    ("Email me at lena.fischer@bio-example.ca if you have the protocol for Western blot transfer at 100 V for 1 hour.",
     [("EMAIL_ADDRESS", "lena.fischer@bio-example.ca")], ["Western blot", "100 V"]),
    ("Why does the BRCA1 gene increase the risk of cancer when mutated? My student number is 301044219.",
     [("STUDENT_ID", "301044219")], ["BRCA1"]),
    ("Dr. Yusuf Demir said the enzyme kinetics of lactase follow Michaelis-Menten. Can you show Km and Vmax from my data? Call me: 613-555-0126.",
     [("PERSON", "Yusuf Demir"), ("PHONE_NUMBER", "613-555-0126")], ["Michaelis-Menten", "Km", "Vmax"]),
    ("In the E. coli growth curve lab, my OD600 plateaued at 1.8 after 6 hours. I'm Sophie Lavoie, section B. Is the stationary phase reached?",
     [("PERSON", "Sophie Lavoie")], ["E. coli", "OD600"]),
    ("What causes the lac operon to turn on when lactose is present? (Niamh O'Sullivan, ID 300582771)",
     [("PERSON", "Niamh O'Sullivan"), ("STUDENT_ID", "300582771")], ["lac operon"]),
    ("The freezer log says the HeLa stock was moved by tomas.novak@cellbio-example.org. Can I thaw it at 37 C right away?",
     [("EMAIL_ADDRESS", "tomas.novak@cellbio-example.org")], ["HeLa", "37 C"]),
    ("How does CRISPR-Cas9 find its target? Please reply to Ayesha Khan, 343-555-0163, I have a quiz tomorrow.",
     [("PERSON", "Ayesha Khan"), ("PHONE_NUMBER", "343-555-0163")], ["CRISPR-Cas9"]),
    ("I saved the sequencing results on my laptop at 10.0.5.77 and the lab server can't read them. How do I share FASTQ files?",
     [("INTERNAL_ADDRESS", "10.0.5.77")], ["FASTQ"]),
    ("Participant P-117 from our class survey, Daniel Okoro, answered 4 on the Likert scale. How do I code ordinal data in R?",
     [("PERSON", "Daniel Okoro")], ["Likert", "ordinal"]),
    ("My Dropbox link for the microscopy images is https://www.dropbox.com/sh/fakeabc123/notreal?token=FAKEtok99 and my TA says it is broken. How should the scale bar be set?",
     [("SECRET", "FAKEtok99")], ["scale bar"]),
    ("Why do the ribosomes of prokaryotes sediment at 70S while eukaryotic ones sediment at 80S? Asking as Hana Svoboda, student no. 300377410.",
     [("PERSON", "Hana Svoboda"), ("STUDENT_ID", "300377410")], ["70S", "80S"]),
    ("Our group's analysis repo is github.com/bio2200-group5/rnaseq-pipeline, please look at why DESeq2 fails on the count matrix.",
     [("REPO_URL", "github.com/bio2200-group5/rnaseq-pipeline")], ["DESeq2"]),
    ("Please explain Mendel's second law. I am Rafael Moreira and my email is rafa.moreira@mail-example.ca.",
     [("PERSON", "Rafael Moreira"), ("EMAIL_ADDRESS", "rafa.moreira@mail-example.ca")], ["Mendel"]),
    # negatives with biology/medical vocabulary that is not personal data
    ("What is the difference between type 1 and type 2 diabetes at the level of insulin signalling?", [], ["insulin", "type 1"]),
    ("Blood group inheritance: if one parent is AB and the other is O, which blood types can the children have?", [], ["AB", "blood types"]),
    ("In the tumour grading lab, what do grade 1, grade 2 and grade 3 mean in terms of differentiation?", [], ["grade 3", "differentiation"]),
    ("A buffer at pH 7.4 with 150 mM NaCl is used for the assay; why not use pH 5?", [], ["pH 7.4", "150 mM"]),
    ("How is the sickle cell allele maintained in malaria regions? Explain heterozygote advantage.", [], ["sickle cell", "heterozygote"]),
    ("The primer sequence 5'-ATGCGTACGTTAGC-3' has a melting temperature of 58 C. How do I calculate it?", [], ["5'-ATGCGTACGTTAGC-3'", "58 C"]),
    ("Explain how antibiotics like penicillin target bacterial cell walls but not human cells.", [], ["penicillin"]),
    ("What is the patient zero concept in epidemiology and why do we use R0 = 2.5 in models?", [], ["R0", "2.5"]),
    ("What does a heart rate of 60 to 100 beats per minute at rest tell us in general about cardiac physiology?", [], ["60 to 100"]),
    ("Which species name is correct: Homo sapiens or Homo sapiens sapiens? The textbook uses Linnaeus' system.", [], ["Homo sapiens", "Linnaeus"]),
    ("The mitochondrial DNA of the sample was 16,569 base pairs long. Why is it inherited maternally?", [], ["16,569", "mitochondrial"]),
    ("What are the stages of mitosis and what is checked at the G2/M checkpoint?", [], ["mitosis", "G2/M"]),
    ("In the Krebs cycle, how many NADH and FADH2 are produced per acetyl-CoA?", [], ["Krebs", "NADH"]),
    ("What is the role of the p53 protein, sometimes called the guardian of the genome?", [], ["p53"]),
    ("Why is vaccination more effective than natural infection for building herd immunity at 95 percent coverage?", [], ["herd immunity", "95 percent"]),
]

GENERAL = [
    ("Hi, I'm Brandon Whitfield (ID 300615028). Can you explain the difference between nominal and real GDP?",
     [("PERSON", "Brandon Whitfield"), ("STUDENT_ID", "300615028")], ["nominal", "real GDP"]),
    ("Please send my essay feedback to isabelle.tremblay@mail-example.ca. What makes a thesis statement arguable?",
     [("EMAIL_ADDRESS", "isabelle.tremblay@mail-example.ca")], ["thesis statement"]),
    ("My phone is 613-555-0188; I missed the lecture on supply and demand curves. Can you summarise the equilibrium idea?",
     [("PHONE_NUMBER", "613-555-0188")], ["supply and demand", "equilibrium"]),
    ("I live at 42 Maple Crescent, Ottawa, K1N 7B2, and cannot come to campus. How does the Keynesian multiplier work?",
     [("ADDRESS", "42 Maple Crescent"), ("POSTAL_CODE", "K1N 7B2")], ["Keynesian multiplier"]),
    ("My professor Dr. Alistair Mackenzie gave me a 62 on the midterm. How can I improve my argument structure?",
     [("PERSON", "Alistair Mackenzie"), ("GRADE", "62")], ["argument structure"]),
    ("Born on 14/03/2004, I am a mature student; what is the difference between a primary and a secondary source?",
     [("DATE_OF_BIRTH", "14/03/2004")], ["primary", "secondary source"]),
    ("Zainab Idris, student number 301377845: why did the Roman Republic turn into an empire?",
     [("PERSON", "Zainab Idris"), ("STUDENT_ID", "301377845")], ["Roman Republic"]),
    ("My Wi-Fi password for the library is Campus!Fake2026 -- is it OK that it is on a sticky note? Also, what is cognitive dissonance?",
     [("SECRET", "Campus!Fake2026")], ["cognitive dissonance"]),
    ("Whom should I cite for the Gini coefficient? Contact: +1 819 555 0134. I am Pierre-Luc Gagnon.",
     [("PHONE_NUMBER", "+1 819 555 0134"), ("PERSON", "Pierre-Luc Gagnon")], ["Gini coefficient"]),
    ("In group work, Valentina Cruz did not answer our messages. What does social loafing mean?",
     [("PERSON", "Valentina Cruz")], ["social loafing"]),
    ("I am student 300290416 and I got 71% on the quiz. What is the difference between mean and median?",
     [("STUDENT_ID", "300290416"), ("GRADE", "71%")], ["mean", "median"]),
    ("Send the reading list to oscar.lindqvist@uni-example.se please. What is a Gantt chart used for?",
     [("EMAIL_ADDRESS", "oscar.lindqvist@uni-example.se")], ["Gantt chart"]),
    ("My health card number is 4821-337-905-XY, can I use it as ID for the exam room? Also, define opportunity cost.",
     [("HEALTH_CARD", "4821-337-905-XY")], ["opportunity cost"]),
    ("Harpreet Gill here. What is the main thesis of Rawls' theory of justice?",
     [("PERSON", "Harpreet Gill")], ["Rawls"]),
    ("Mail the certificate to 17 Birchwood Ave, Gatineau J8X 2K9. What are the five forces in Porter's model?",
     [("ADDRESS", "17 Birchwood Ave"), ("POSTAL_CODE", "J8X 2K9")], ["Porter"]),
    # negatives
    ("What was the GDP growth of 3.2 percent in 2019 compared with 1.8 percent in 2020?", [], ["3.2 percent", "2019"]),
    ("Who wrote Pride and Prejudice and what are its main themes of class and marriage?", [], ["Pride and Prejudice"]),
    ("Explain the Treaty of Versailles of 1919 and why it was called a Carthaginian peace.", [], ["Treaty of Versailles", "1919"]),
    ("How do I cite a book in APA 7th edition? The chapter is on pages 112-130.", [], ["APA 7th edition", "112-130"]),
    ("What is the difference between a Type I and a Type II error in hypothesis testing with alpha = 0.05?", [], ["Type I", "0.05"]),
    ("Define the Pareto principle: do 20 percent of the causes produce 80 percent of the effects?", [], ["Pareto principle", "80 percent"]),
    ("Can you explain Kant's categorical imperative and the second formulation about humanity?", [], ["categorical imperative"]),
    ("The course syllabus says assignment 3 is worth 15 percent and is due on 2026-03-15. How should I plan my time?", [], ["15 percent", "2026-03-15"]),
    ("What is the grade point average scale at most universities, and how is a weighted GPA computed in general?", [], ["weighted GPA"]),
    ("Why did the Industrial Revolution start in Britain in the 1760s and not in France?", [], ["Industrial Revolution", "1760s"]),
]


def build(rows: list, prefix: str) -> list[dict]:
    out = []
    for i, (text, ents, keep) in enumerate(rows, 1):
        for _typ, span in ents:
            assert span in text, (prefix, i, span)
        for k in keep:
            assert k in text, (prefix, i, k)
        out.append({"id": f"{prefix}{i:03d}", "group": P if ents else N, "text": text,
                    "entities": [{"type": t, "text": s} for t, s in ents], "keep": keep,
                    "personal_health": False})
    return out


SETS = {"ece_holdout": (ECE, "EH"), "cs_holdout": (CS, "CH"), "life_holdout": (LIFE, "LH"),
        "general_holdout": (GENERAL, "GH")}

if __name__ == "__main__":
    for name, (rows, prefix) in SETS.items():
        cases = build(rows, prefix)
        (HERE / f"{name}.jsonl").write_text(
            "\n".join(json.dumps(c, ensure_ascii=False) for c in cases) + "\n", encoding="utf-8")
        pos = sum(c["group"] == P for c in cases)
        print(name, len(cases), "positive", pos, "negative", len(cases) - pos)
