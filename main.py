from dotenv import load_dotenv
from db.singleton import init_engine, get_session_manager
from ingestion_pipeline.semantic_effort.qwen import QwenEmbeddingProcess
from jobs.scheduler import pipe_jobs

load_dotenv()

if __name__ == "__main__":
    load_dotenv()
    embeeding_model = QwenEmbeddingProcess()

    # 1. Initialize DB (triggers auto-migration in dev mode)
    init_engine()
    s = get_session_manager()
    pipe_jobs(embeeding_model)


# # Points to rembebmer:
# # - we need to cite the context email and reasoing of selecting the stragey
# # - give all the information to the user, subject email name and intent
# # - use citation when reasoing the draft or possible plans this will lead to more concreate and closed approch
# # - are we presuming to take any action? how to do avoid writting if we are not sure
# # - create one multi-agent workflow
# # - think how are we managing memory - org informaton, lingustic changes, specfic style changes
# #
# # - improve schemas and db calls
# # - handle threads, save threads and avoid if thread is done
