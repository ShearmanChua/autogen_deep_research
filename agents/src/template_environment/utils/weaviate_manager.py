import copy
import os
from typing import List, Union

import numpy
import torch
import weaviate


class VectorManager:
    TYPE_MAP = {
        "int": ["int"],
        "float": ["number"],
        "double": ["number"],
        "str": ["text"],
        "bool": ["boolean"],
        "datetime": ["date"],
        "list[int]": ["int[]"],
        "list[str]": ["text[]"],
        "list[float]": ["number[]"],
        "list[double]": ["number[]"],
        "torch.tensor": "",
        "numpy.ndarray": "",
    }

    def __init__(self) -> None:
        """
        Set up the connection

        INPUT: None
        ------------------------------------

        RETURNS: None
        ------------------------------------
        """
        self._client = weaviate.Client(
            (
                f"http://{os.environ.get('WEAVIATE_HOST')}:"
                f"{os.environ.get('WEAVIATE_PORT')}"
            )
        )

    def _traverse_map(self, schema: dict) -> List:
        """
        Restructure the schema

        INPUT:
        ------------------------------------
        schema:             Schema for each document
                            example: {
                                "doc_id": "str",
                            }

        RETURNS:
        ------------------------------------
        List:               List of dictionary for the field mapping
                            example: [{
                                "name" : "doc_id",
                                "dataType" : ["text"],
                                }]
        """
        temp = []
        for k, v in schema.items():
            try:
                self.TYPE_MAP.get(v)
                if v != "":
                    if v == "str":
                        temp.append(
                            {
                                "indexSearchable": True,
                                "name": k,
                                "dataType": self.TYPE_MAP[v],
                            }
                        )
                    else:
                        temp.append({"name": k, "dataType": self.TYPE_MAP[v]})
            except Exception as e:
                print(e)
                return []
        return temp

    def _id2uuid(self, collection_name: str, doc_id: str) -> dict:
        """
        Convert doc_id to uuid

        INPUT:
        ------------------------------------
        collection_name:    Name of collection
                            example:  'Faces'
        doc_id:             id of document
                            example: '72671'

        RETURNS:
        ------------------------------------
        Dict:               Dictionary with the uuid or errors
                            example: {
                                'uuid': '1fbf7a0f-1904-4c21-afd8-6bda380e51fd'
                            }
        """
        collection_name = collection_name.capitalize()
        if self._exists(collection_name, doc_id):
            where_filter = {
                "operator": "Equal",
                "valueText": doc_id,
                "path": ["doc_id"],
            }
            query_result = (
                self._client.query.get(collection_name, ["doc_id", "_additional {id}"])
                .with_where(where_filter)
                .do()
            )
            uuid = query_result["data"]["Get"][collection_name][0]["_additional"]["id"]
            return {"uuid": uuid}
        return {"errors": f"id: {doc_id} is not found"}

    def _exists(self, collection_name: str, doc_id: str) -> bool:
        """
        Convert doc_id to uuid

        INPUT:
        ------------------------------------
        collection_name:    Name of collection
                            example:  'Faces'
        doc_id:             id of document
                            example: "72671"

        RETURNS:
        ------------------------------------
        bool:               If the doc_id exists in the collection
                            example: True or False
        """
        collection_name = collection_name.capitalize()
        where_filter = {"operator": "Equal", "valueText": doc_id, "path": ["doc_id"]}
        response = (
            self._client.query.get(collection_name, ["doc_id", "_additional {id}"])
            .with_where(where_filter)
            .do()
        )
        if "data" in response and len(response["data"]["Get"][collection_name]) == 1:
            return True
        return False

    def _get_searchable_fields(self, collection_name: str) -> list:
        """
        Obtain properties and fields of a specific collection

        INPUT:
        ------------------------------------
        collection_name:    Name of collection
                            example:  'Faces'

        RETURNS:
        ------------------------------------
        list:               List of all fields that have indexSearchable set to True
        """
        collection_name = collection_name.capitalize()
        for collection in self._client.schema.get()["classes"]:
            if collection["class"] == collection_name:
                return [
                    x["name"] for x in collection["properties"] if x["indexSearchable"]
                ]
        return []

    def delete_collection(self, collection_name: str) -> dict:
        """
        Delete the entire collection

        INPUT:
        ------------------------------------
        collection_name:    Name of collection
                            example:  'Faces'

        RETURNS:
        ------------------------------------
        dict:               Dictionary with the success code 200 or errors
                            example: {'response': "200"}
        """
        collection_name = collection_name.capitalize()
        try:
            self._client.schema.delete_class(collection_name)
        except Exception as e:
            return {"response": f"{e}"}
        return {"response": "200"}

    def delete_document(self, collection_name: str, doc_id: str) -> dict:
        """
        Delete a document in a weaviate class

        INPUT:
        ------------------------------------
        collection_name:    Name of collection
                            example:  'Faces'
        doc_id:             id of document
                            example: "72671"

        RETURNS:
        ------------------------------------
        dict:               Dictionary with the success code 200 or errors
                            example: {'response': "200"}
        """
        collection_name = collection_name.capitalize()
        uuid = self._id2uuid(collection_name, doc_id)
        if "uuid" in uuid:
            try:
                self._client.data_object.delete(
                    uuid=uuid["uuid"], class_name=collection_name
                )
                return {"response": "200"}
            except Exception as e:
                return {"response": f"Unknown error with error message -> {e}"}
        return {"response": uuid["errors"]}

    def create_collection(self, collection_name: str, schema: dict) -> dict:
        """
        Create a collection of documents

        INPUT:
        ------------------------------------
        collection_name:    Name of collection
                            example:  'Faces'
        schema:             Schema for each document
                            example: {
                                "doc_id": str,
                            }

        RETURNS:
        ------------------------------------
        dict:               Dictionary with the success code 200 or errors
                            example: {'response': "200"}
        """
        collection_name = collection_name.capitalize()
        if not schema.get("doc_id"):
            return {"response": "Lack of doc_id as an attribute in property"}
        properties = self._traverse_map(schema)
        if properties == []:
            return {"response": "Unknown data type in the field"}
        document_schema = {
            "class": collection_name,
            "vectorizer": "none",
            "properties": properties,
        }
        try:
            self._client.schema.create_class(document_schema)
        except Exception as e:
            return {"response": f"Unknown error with error message -> {e}"}
        return {"response": "200"}

    def _create_single_document(self, collection_name: str, document: dict) -> dict:
        """
        Create a document in a specified collection

        INPUT:
        ------------------------------------
        collection_name:    Name of collection
                            example:  'Faces'
        document:           A single document. To update embedding, include 'vector'
                            key in the dict.
                            example: {
                                "doc_id": "72671",
                                "vector": []
                            }

        RETURNS:
        ------------------------------------
        dict:               Dictionary with the success code 200 or errors
                            example: {'response': "200"}
        """
        collection_name = collection_name.capitalize()
        embedding = None
        # Check if the doc_id attribute exist
        if not document.get("doc_id"):
            return {"response": "Lack of doc_id as an attribute in property"}
        # Check if the id exist
        id_exists = self._exists(collection_name, document["doc_id"])
        if id_exists:
            return {"response": "This id already existed, please use update instead"}
        # Create document
        if "vector" in document:
            valid_vec_type = [numpy.ndarray, torch.Tensor, list]
            if not type(document["vector"]) in valid_vec_type:
                return {
                    "response": (
                        "Invalid vector type. Supported vector types:"
                        " numpy.ndarray, torch.Tensor, list"
                    )
                }
            embedding = document["vector"]
            document.pop("vector")
        try:
            self._client.data_object.create(document, collection_name, vector=embedding)
        except Exception as e:
            if "vector lengths don't match" in str(e):
                self.delete_document(collection_name, document["doc_id"])
                return {"response": "Mismatch vector length, creation failed"}
            else:
                return {"response": f"{e}"}
        return {"response": "200"}

    def create_document(
        self, collection_name: str, documents: Union[list, dict]
    ) -> dict:
        """
        Batch create documents in a specified collection to reduce the time taken to
        create a large set of documents. If any documents already exists, it will be
        skipped and the id will be returned in the response.

        INPUT:
        ------------------------------------
        collection_name:    Name of collection
                            example shape:  'Faces'
        documents:          One or more documents. To update embedding, include 'vector'
                            key in the dict.
                            example: {
                                "doc_id": "72671",
                                "vector": []
                            }

        RETURNS:
        ------------------------------------
        dict:               Dictionary with the success code 200 or errors, along with
                            the list of existing document IDs
                            example: {'response': "200",
                                      'existing_documents': ['72671', '72672']]
                                     }

        """
        collection_name = collection_name.capitalize()
        if isinstance(documents, dict):
            return self._create_single_document(collection_name, documents)
        if len(documents) == 1:
            return self._create_single_document(collection_name, documents[0])

        self._client.batch.configure(
            batch_size=40,
            dynamic=False,
            connection_error_retries=3,
            timeout_retries=3,
            callback=weaviate.util.check_batch_result,
        )

        existing_documents = []

        with self._client.batch as batch:
            for i, doc in enumerate(documents):
                embedding = None
                # Check if the doc_id attribute exist
                if not doc.get("doc_id"):
                    return {
                        "response": (
                            f"Lack of doc_id as an attribute in property for doc {i}"
                        )
                    }
                # Check if the id exist
                id_exists = self._exists(collection_name, doc["doc_id"])
                if id_exists:
                    existing_documents.append(doc["doc_id"])
                    continue

                if "vector" in doc:
                    valid_vec_type = [numpy.ndarray, torch.Tensor, list]
                    if not type(doc["vector"]) in valid_vec_type:
                        return {
                            "response": (
                                "Invalid vector type. Supported vector types: "
                                "numpy.ndarray, torch.Tensor, list"
                            )
                        }
                    embedding = doc["vector"]
                    doc.pop("vector")

                try:
                    # Batch auto-creates when full.
                    # Last batch automatically added at end of `with` block
                    batch.add_data_object(doc, collection_name, vector=embedding)
                except Exception as e:
                    if "vector lengths don't match" in str(e):
                        print("response: Mismatch vector length, creation failed")
                    else:
                        return {"response": f"{e}"}

        return {"response": "200", "existing_documents": existing_documents}

    def read_document(self, collection_name: str, doc_id: str) -> dict:
        """
        Return a matching document in a specified collection

        INPUT:
        ------------------------------------
        collection_name:    Name of collection
                            example:  'Faces'
        doc_id:             id of document
                            example: "72671"

        RETURNS:
        ------------------------------------
        dict:               Dictionary with the success code 200 or errors
                            example: {'response': "200"}
        """
        collection_name = collection_name.capitalize()
        if not self._exists(collection_name, doc_id):
            return {
                "response": (
                    "Attempt to read a non-existent document. " "No reading is done"
                )
            }
        # Create filter and search
        uuid = self._id2uuid(collection_name, doc_id)
        if "uuid" in uuid:
            return {
                "response": self._client.data_object.get_by_id(
                    uuid=uuid["uuid"], class_name=collection_name, with_vector=True
                )
            }
        return {"response": uuid["errors"]}

    def get_top_k(
        self,
        collection_name: str,
        target_embedding: Union[list, numpy.ndarray, torch.Tensor],
        query_string: str = "",
        top_k: int = 1,
        alpha: int = 1,
    ) -> dict:
        """
        Return the dictionary with the response key holding the list of near documents

        INPUT:
        ------------------------------------
        collection_name:    Name of collection
                            example:  'Faces'
        query_string:       Query string for bm25 text similarity search
                            example: "a dog standing next to an orange cat"
        target_embedding:   Query embedding to find document with high cosine similarity
                            example: torch.Tensor([0.5766745, ..., 0.013553977])
        top_k:              integer value for the number of documents to return.
                            Default is 1
                            example: 3
        alpha:              Weight of BM25 or vector search. 0 for pure keyword search,
                            1 for pure vector search. Default is pure vector search.

        RETURNS:
        ------------------------------------
        dict:               Dictionary with list or errors
                            example: {
                                response: [{
                                    'class': 'Faces',
                                    'creationTimeUnix': 1671076617122,
                                    'id': '9d62d87b-bb17-4736-8714-e1455ffa2b01',
                                    'lastUpdateTimeUnix': 1671076617122,
                                    'properties': {'doc_id': '11', 'new': '2'},
                                    'vector': [0.5766745, ..., 0.013553977],
                                    'vectorWeights': None,
                                    'certainty': 0.9999999403953552
                                }]
                            }

        """
        collection_name = collection_name.capitalize()
        if top_k < 1:
            return {"response": "Invalid top_k"}
        if alpha == 1:
            query_vector = {"vector": target_embedding}
            res = (
                self._client.query.get(
                    collection_name, ["doc_id", "_additional {certainty, id}"]
                )
                .with_near_vector(query_vector)
                .do()
            )

        else:
            query_vector = (
                target_embedding.tolist()
            )  # with_hybrid wants the vector as a list
            res = (
                self._client.query.get(collection_name, ["doc_id"])
                .with_hybrid(
                    query_string,
                    vector=query_vector,
                    alpha=alpha,
                    properties=self._get_searchable_fields(collection_name),
                )
                .with_additional(["score"])
                .do()
            )
        if "errors" in res:
            return {"response": res["errors"]}
        try:
            limit = min(top_k, len(res["data"]["Get"][collection_name]))
            top_id = res["data"]["Get"][collection_name][:limit]
            top_results = [
                self.read_document(collection_name, document["doc_id"])
                for document in top_id
            ]
            for document, res in zip(top_id, top_results):
                if alpha == 1:
                    res["certainty"] = document["_additional"]["certainty"]
                else:
                    res["certainty"] = document["_additional"]["score"]
            return {"response": top_results}
        except Exception as e:
            return {"response": f"{e}"}

    def update_document(
        self, collection_name: str, doc_id: str, document: dict
    ) -> dict:
        """
        Update a document in a specified collection

        INPUT:
        ------------------------------------
        collection_name:    Name of collection
                            example shape:  'Faces'
        doc_id:             id of document to be updated
        document:           dictionary format of the updated document
                            {
                                'doc_id': '4848272',
                                'vector': torch.Tensor([[
                                    1, 2, ..., 512
                                ]]),
                                'name': 'Trump'
                            }

        RETURNS:
        ------------------------------------
        dict:               Dictionary with the success code 200 or errors
                            example: {'response': "200"}
        """
        collection_name = collection_name.capitalize()
        if not self._exists(collection_name, doc_id):
            return {
                "response": (
                    "Attempt to update a non-existent document. " "No reading is done"
                )
            }
        if "doc_id" in document:
            del document["doc_id"]
        if len(document.keys()) == 0:
            return {"response": "No properties to update."}
        uuid = self._id2uuid(collection_name, doc_id)
        if "uuid" in uuid:
            temp = copy.deepcopy(document)
            if "vector" in document.keys():
                new_vector = temp["vector"]
                del temp["doc_id"]
                del temp["vector"]
                previous_vector = self._client.data_object.get_by_id(
                    uuid=uuid["uuid"], class_name=collection_name, with_vector=True
                )["vector"]
                try:
                    self._client.data_object.update(
                        data_object=temp,
                        class_name=collection_name,
                        uuid=uuid["uuid"],
                        vector=new_vector,
                    )
                    return {"response": "200"}
                except Exception as e:
                    if "vector lengths don't match" in str(e):
                        document["vector"] = previous_vector
                        self.update_document(collection_name, document)
                        return {"response": "Mismatch vector length, updating failed"}
                    else:
                        return {"response": f"{e}"}
            else:
                del temp["doc_id"]
                try:
                    self._client.data_object.update(
                        data_object=temp,
                        class_name=collection_name,
                        uuid=uuid["uuid"],
                    )
                    return {"response": "200"}
                except Exception as e:
                    return {"response": f"{e}"}
        return {"response": uuid["errors"]}
