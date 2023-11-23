# hidden (no-copy-paste area)

import cam
import random

class ExternalTaskWorker:
    def __init__(self):  
        tenant_id = "rolex"
        topic = "newPrescription"      
        self.worker = cam.Client("https://digibp.herokuapp.com/engine-rest")
        # define the topic and your tenant id in the variables
        # the second parameter to the subscribe() method should match the name of the callback function
        # subscribe() calls the fetchAndLock 
        self.worker.subscribe(topic, self.get_surprise_menu_callback, tenant_id)
        self.worker.polling()

    def get_surprise_menu_callback(self, taskid, response):   
        print("processing task with id: " + taskid)     
        patient_name = response[0]['variables']['patient_name']['value']  
        print("patientName: " + patient_name)               
        variables = {"patient_name": patient_name}
               
        try:
            print("try complete")
            status_code = self.worker.complete(taskid, **variables)
            if status_code == 500:
                print("task failed to complete, fail task")
                self.worker.failure(taskid)
        except:
            print("call failure")
            self.worker.failure(taskid)
        
        
# the following line of code will make subscribe to camunda tasks
if __name__ == '__main__':
    ExternalTaskWorker()