import cam
import random

class ExternalTaskWorker:
    def __init__(self):  
        tenant_id = "rolex"
        prescription_topic = "newPrescriptionForm"          
        self.worker = cam.Client("https://digibp.herokuapp.com/engine-rest")
        # define the topic and your tenant id in the variables
        # the second parameter to the subscribe() method should match the name of the callback function
        # subscribe() calls the fetchAndLock 
        self.worker.subscribe(prescription_topic, self.get_prescription_callback, tenant_id)
        self.worker.polling()

    def get_prescription_callback(self, taskid, response):   
        print("processing task with id: " + taskid)
        patient_name = response[0]['variables']['patient_name']['value'] 
        if patient_name == "[Collection]":            
            self.worker.failure(taskid)
            return

        print("patientName: " + str(patient_name))
        variables = {"patient_name": patient_name, "process_instance_id": taskid}               
        try:            
            status_code = self.worker.complete(taskid, **variables)
            if status_code == 500:
                print("task failed to complete, fail task")
                self.worker.failure(taskid)
        except:
            print("call failure")
            self.worker.failure(taskid)
#            ExternalTaskWorker()
        
        
# the following line of code will make subscribe to camunda tasks
if __name__ == '__main__':
    ExternalTaskWorker()