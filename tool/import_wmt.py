"""I need to take WMT xml file, and upload it to the server
using this API:

curl -X POST http://localhost:8000/api/v1/namespaces/default/translations-runs/ \
                                         -H "Content-Type: application/json" \
                                         -d '{
                                       "dataset_name": "example_dataset",
                                       "dataset_source_lang": "en",
                                       "dataset_target_lang": "fr",
                                       "segments": [
                                         {
                                           "src": "Hello, world!",
                                           "tgt": "Bonjour, le monde!"
                                         },
                                         {
                                           "src": "How are you?",
                                           "tgt": "Comment ça va?"
                                         }
                                       ]
                                     }'
"""

import xml.etree.ElementTree as ET
import requests
import json
import os

INPUT_FILE = "/home/mhn/workspace/wmttest2024.en-cs.all.xml"

API_URL = "http://localhost:8000/api/v1/namespaces/default/translations-runs/"

NAMESPACE_NAME = "default"
DATASET_SOURCE_LANG = "en"
DATASET_TARGET_LANG = "cs"

def parse_wmt_xml_by_system_with_ref(input_file):
    tree = ET.parse(input_file)
    root = tree.getroot()
    systems = {}
    # Iterate over all <doc> elements
    for doc in root.findall('.//doc'):
        # Build a mapping of seg id to reference text
        ref_map = {}
        ref_elem = doc.find('ref')
        if ref_elem is not None:
            for seg in ref_elem.findall('.//seg'):
                seg_id = seg.get('id')
                if seg_id:
                    ref_map[seg_id] = seg.text.strip() if seg.text else ''
        # For each <hyp system="..."> in <doc>
        for hyp in doc.findall('hyp'):
            sysid = hyp.get('system') or 'default_system'
            segments = []
            for seg in hyp.findall('.//seg'):
                src_id = seg.get('id')
                tgt = seg.text
                if tgt is None or src_id is None:
                    continue
                # Find the corresponding source segment by id
                src_elem = doc.find(f"src//seg[@id='{src_id}']")
                src = src_elem.text if src_elem is not None else None
                if src is None:
                    continue
                ref = ref_map.get(src_id, None)
                segments.append({"src": src.strip(), "tgt": tgt.strip(), "ref": ref})
            if segments:
                if sysid not in systems:
                    systems[sysid] = []
                systems[sysid].extend(segments)
    return systems

def main():
    systems = parse_wmt_xml_by_system_with_ref(INPUT_FILE)
    if not systems:
        print("No systems found in the XML file.")
        return
    headers = {"Content-Type": "application/json"}
    dataset_name = os.path.splitext(os.path.basename(INPUT_FILE))[0]
    for sysid, segments in systems.items():
        print(len(set([seg['src'] for seg in segments])), "unique source segments found.")
        print(len(set([seg['tgt'] for seg in segments])), "unique target segments found.")
        print(len(set([seg['ref'] for seg in segments if 'ref' in seg])), "unique reference segments found.")
        print(len(segments), "segments found.")
        # exit()
        payload = {
            "namespace_name": NAMESPACE_NAME,
            "dataset_name": dataset_name,
            "dataset_source_lang": DATASET_SOURCE_LANG,
            "dataset_target_lang": DATASET_TARGET_LANG,
            "segments": segments,
            "config": {"system_name": sysid}
        }
        print(f"Submitting system: {sysid} with {len(segments)} segments...")
        response = requests.post(API_URL, headers=headers, data=json.dumps(payload))
        print(f"System: {sysid} | Status code: {response.status_code}")
        print(f"Response: {response.text}\n")

if __name__ == "__main__":
    main()
