import requests
import json


def test_eval():
    url = "http://localhost:8000/run_evaluations"
    body = {
        "trace_id": "caff362f4f72ae50db329105402c0dad",
        "project_name": "PLACEHOLDER_project_name",
    }
    response = requests.post(url, json=body)
    print(response.json())
    assert response.status_code == 200


def test_retrieve_completed_evals():
    url = "http://localhost:8000/evaluations"
    response = requests.get(url)
    print(response.json())
    assert response.status_code == 200


def test_retrieve_eval_by_id():
    url = "http://localhost:8000/evaluations/1"
    response = requests.get(url)
    print(json.dumps(response.json(), indent=4))
    assert response.status_code == 200


if __name__ == "__main__":
    # test_retrieve_completed_evals(
    test_retrieve_eval_by_id()
