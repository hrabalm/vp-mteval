"""Components that takes care of uploading the results of a translation run.

Challenges:
- we need to ensure and validate that only dataset with matching segments and
  structure are connected together. Because we want to support delayed uploads,
  it is made more challenging, because we might end up with different datasets
  stored with the same name. Current solution to this is based on the dataset
  having a fingerprint created from canonicalized JSON. Datasets with the same
  name in the database are supposed to be differentiated by appending -num to
  the name when shown to the user.
- the uploaded data is supposed to be immutable - we also want to link added
  entries to the UUID of the transaction that added them.
"""

def upload_translation_run(

):
    pass
