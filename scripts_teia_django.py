# Script complet pour transformer un DOCX friendly en ZIP QTI (QI en GIFT + QROC en XML) + KFP (QTI XML)

from docx import Document
import re
import html
import zipfile
import os
import argparse
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString

# Paramètres globaux par défaut
invisible = ['\u00A0', '\u200B', '\u200C', '\u200D', '\u2060', '\uFEFF']
paragraph_headers = ("[QI]", "[KFP]", "[DP]")
clean = lambda text: ''.join(c for c in text if c not in invisible)

def parse_docx(path):
    doc = Document(path)
    paragraphs = [clean(p.text.strip())for p in doc.paragraphs]
    qi_list, dp_list = [], []
    i = 0
    while i < len(paragraphs):
        while i < len(paragraphs) - 1 and paragraphs[i] not in paragraph_headers:
          i += 1
        if i < len(paragraphs) - 1 and paragraphs[i] in "[QI]":
            i += 1
            question_text = paragraphs[i]  
            choices = []
            i += 1
            while i < len(paragraphs) and paragraphs[i] not in paragraph_headers:
                line_raw = paragraphs[i]
                is_correct = line_raw.endswith("*")
                line = line_raw
                text = re.sub(r"\s*\*$", "", line).strip()
                if text:
                    choices.append((text, is_correct))
                i += 1
            nb_correct = sum(1 for _, c in choices if c)
            if nb_correct == 0:
                qtype = "qroc"
            elif nb_correct == 1:
                qtype = "qru"
            else:
                qtype = "qrm"
            qi_list.append({"type": qtype, "question": question_text, "choices": choices})

        elif i < len(paragraphs) and paragraphs[i] == "[DP]":
            i += 1
            while i < len(paragraphs) -1 and not paragraphs[i].strip():
              i += 1
            vignette = paragraphs[i]
            i += 1
            questions = []
            while i < len(paragraphs) and paragraphs[i] not in paragraph_headers:
                if paragraphs[i].lower().startswith("q:"):
                    q_text = paragraphs[i]
                    q_text = q_text[2:].strip()
                    i += 1
                    subchoices = []
                    while i < len(paragraphs) - 1 and paragraphs[i] not in (paragraph_headers) and not paragraphs[i].lower().startswith("q:"):
                        line_raw = paragraphs[i]
                        if not line_raw.strip():
                            i += 1
                            continue
                        is_correct = line_raw.endswith("*")
                        text = re.sub(r"\s*\*$", "", line_raw).strip()
                        subchoices.append((text, is_correct))
                        i += 1
                    nb_correct = sum(1 for _, c in subchoices if c)
                    if nb_correct == 0:
                        qtype = "qroc"
                    elif nb_correct == 1:
                        qtype = "qru"
                    else:
                        qtype = "qrm"
                    questions.append({"type": qtype, "question": q_text, "choices": subchoices})
                else:
                    i += 1
            dp_list.append({"vignette": vignette, "questions": questions})
        else:
            i += 1
    return qi_list, dp_list

def generate_gift(qi_list, output_dir, discipline, annee, session, titulaire):
    """
    Crée un fichier GIFT à partir des questions et le compresse en ZIP.
    Retourne le chemin complet vers le ZIP créé.
    """
    gift_lines = []
    for idx, q in enumerate(qi_list, 1):
        nom = f"{discipline}-{annee}-{session}-QI N°{idx}-{titulaire}"
        gift_lines.append(f"::{nom}::{q['question']} {{")
        for choice, is_correct in q['choices']:
            if q["type"] == "qrm":
                if choice:
                    percent = "100" if is_correct else "-100"
                    gift_lines.append(f"~%{percent}% {choice}")
            elif q["type"] == "qroc":
                if choice:
                    gift_lines.append(f"={choice}")
            elif q["type"] == "qru":
                    percent = "=" if is_correct else "~"
                    gift_lines.append(f"{percent}{choice}") 
        gift_lines.append("}\n")

    # Sauvegarder dans le dossier temporaire
    gift_path = os.path.join(output_dir, "questions.gift")
    with open(gift_path, "w", encoding="utf-8") as f:
        f.write("\n".join(gift_lines))

    # Créer le ZIP
    zip_path = os.path.join(output_dir, "gift_output.zip")
    with zipfile.ZipFile(zip_path, "w") as zipf:
        zipf.write(gift_path, arcname="questions.gift")

    # Supprimer le .gift si tu veux
    os.remove(gift_path)

    return zip_path

def generate_qti_qcm(identifier, title, question_text, choices, type):
    root = Element("assessmentItem", attrib={
        "xmlns": "http://www.imsglobal.org/xsd/imsqti_v2p1",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "identifier": identifier,
        "title": title,
        "adaptive": "false",
        "timeDependent": "false",
        "toolName": "Theia",
        "xsi:schemaLocation": "http://www.imsglobal.org/xsd/imsqti_v2p1 http://www.imsglobal.org/xsd/qti/qtiv2p1/imsqti_v2p1.xsd"
    })
    if type == "qrm":
        response = SubElement(root, "responseDeclaration", identifier="RESPONSE", cardinality="multiple", baseType="identifier")
        correct = SubElement(response, "correctResponse")
    elif type == "qru":
        response = SubElement(root, "responseDeclaration", identifier="RESPONSE", cardinality="single", baseType="identifier")
        correct = SubElement(response, "correctResponse")        
    for i, (_, is_correct) in enumerate(choices):
        if is_correct:
            SubElement(correct, "value").text = f"CHOICE_{6000 + i}"
    outcome = SubElement(root, "outcomeDeclaration", identifier="SCORE", cardinality="single", baseType="integer")
    default = SubElement(outcome, "defaultValue")
    SubElement(default, "value").text = "0"
    body = SubElement(root, "itemBody")
    interaction = SubElement(body, "choiceInteraction", responseIdentifier="RESPONSE", maxChoices=str(sum(1 for _, c in choices if c)))
    prompt = SubElement(interaction, "prompt")
    prompt.text = question_text
    for i, (text, _) in enumerate(choices):
        choice = SubElement(interaction, "simpleChoice", identifier=f"CHOICE_{6000 + i}")
        choice.text = text
    SubElement(root, "responseProcessing", template="http://www.imsglobal.org/question/qti_v2p1/rptemplates/match_correct")
    return parseString(tostring(root, encoding="utf-8")).toprettyxml(indent="  ", encoding="UTF-8")

def generate_qti_qroc(identifier, title, question_text, choices):
    root = Element("assessmentItem", attrib={
        "xmlns": "http://www.imsglobal.org/xsd/imsqti_v2p1",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "identifier": identifier,
        "title": title,
        "adaptive": "false",
        "timeDependent": "false",
        "toolName": "Theia",
        "xsi:schemaLocation": "http://www.imsglobal.org/xsd/imsqti_v2p1 http://www.imsglobal.org/xsd/qti/qtiv2p1/imsqti_v2p1.xsd"
    })
    response = SubElement(root, "responseDeclaration", identifier="RESPONSE", cardinality="single", baseType="string")
    correct = SubElement(response, "correctResponse")
    for val in choices:
        if val.strip():
            SubElement(correct, "value").text = val.strip()
    outcome = SubElement(root, "outcomeDeclaration", identifier="SCORE", cardinality="single", baseType="float")
    default = SubElement(outcome, "defaultValue")
    SubElement(default, "value").text = "0"
    body = SubElement(root, "itemBody")
    SubElement(body, "div").text = html.escape(question_text)
    SubElement(body, "div")
    SubElement(body[-1], "textEntryInteraction", responseIdentifier="RESPONSE", expectedLength="255")
    SubElement(root, "responseProcessing", template="http://www.imsglobal.org/question/qti_v2p1/rptemplates/match_correct")
    return parseString(tostring(root, encoding="utf-8")).toprettyxml(indent="  ", encoding="UTF-8")

def write_dp_pool(dp, output_dir, discipline, annee, session, titulaire, index=1):

    output_zip = f"{output_dir}/QTI_DP_final_{index}.zip"

    dp_title = f"{discipline}-{annee}-{session}-DP N°{index}-{titulaire}"
    dp_vignette = html.escape(f"<p>{dp['vignette']}</p>")
    dp_item_refs, dp_files = [], []
    for idx, question in enumerate(dp["questions"], 1):
        q_type = question["type"]
        question_text = question["question"]
        if q_type == "qroc":
            identifier = f'TEXT_QUESTION_{7872730 + idx}'
        elif q_type == "qrm":
            identifier =  f"MULTIPLECHOICE_QUESTION_{7872730 + idx}"
        elif q_type == "qru":
            identifier =  f"SINGLECHOICE_QUESTION_{7872730 + idx}"
        filename = identifier + ".xml"

        if q_type == "qroc":
            answers = [c[0] for c in question["choices"]]
            xml = generate_qti_qroc(identifier, "Question à Réponse Ouverte et Courte", question_text, answers)
        elif q_type == "qrm":
            xml = generate_qti_qcm(identifier, "Question à réponses multiples", question_text, question["choices"], q_type)
        elif q_type == "qru":
            xml = generate_qti_qcm(identifier, "Question à réponse unique", question_text, question["choices"], q_type)
        with open(filename, "wb") as f:
            f.write(xml)
        dp_files.append(filename)
        dp_item_refs.append(f'''    <assessmentItemRef identifier="{identifier}" required="true" fixed="true" href="{filename}">
        <weight identifier="WEIGHT" value="1"/>
        </assessmentItemRef>''')

    pool_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
    <testPart xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" identifier="DPPOOL_SECTION_DP_{7872730}" navigationMode="linear" submissionMode="individual" xsi:schemaLocation="http://www.imsglobal.org/xsd/imsqti_v2p1 http://www.imsglobal.org/xsd/qti/qtiv2p1/imsqti_v2p1.xsd">
      <assessmentSection identifier="DPPOOL_SECTION_DP_{7872730}" required="false" fixed="false" title="{dp_title}" visible="true" keepTogether="true">
        <rubricBlock view="candidate">
          <div>{dp_vignette}</div>
        </rubricBlock>
    {chr(10).join(dp_item_refs)}
      </assessmentSection>
    </testPart>'''

    with open("pool.xml", "w", encoding="utf-8") as f:
        f.write(pool_xml)
    output_zip = os.path.join(output_dir, f"DP_N_{index}.zip")
    with zipfile.ZipFile(output_zip, "w") as zipf:
        for f in dp_files:
            zipf.write(f, arcname=f)
            os.remove(f)
        zipf.write("pool.xml")
        os.remove("pool.xml")

    return output_zip

def run(input, output_dir, discipline, annee, session, titulaire):
    files = []
    qi_list, dp_list = parse_docx(input)
    print(dp_list)
    if qi_list:
        files.append(generate_gift(qi_list, output_dir,discipline, annee, session, titulaire))
    else:
        print("⚠️ Aucun QI détecté dans le fichier.")
    if not dp_list:
        print("⚠️ Aucun DP détecté dans le fichier.")
    else:
      for i, dp in enumerate(dp_list):
          files.append(write_dp_pool(dp, output_dir, discipline, annee, session, titulaire, index=i+1))
    return files
