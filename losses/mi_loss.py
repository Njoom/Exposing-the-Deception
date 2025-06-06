import logging

import torch
from losses import distance
import torch.nn as nn
from losses.AutomaticWeightedLoss import AutomaticWeightedLoss
import numpy as np

class loss_functions():
    def __init__(self, method='distance', mi_calculator='kl', temperature=1.5, bml_method='auto', scales=[1, 1, 1],
                 gil_loss=False,lil_loss=False,device='cuda:0'):
        self.lil_loss=lil_loss
        self.gil_loss=gil_loss

        loss_num=1
        if gil_loss:
            loss_num+=1
            logging.info("With Global Information Loss")
        if lil_loss:
            loss_num+=1
            logging.info("With Local Information Loss")
        self.balance_loss = AutomaticWeightedLoss(loss_num)  # we have 3 losses

        self.softmax = torch.nn.Softmax(dim=1)
        self.method=method
        self.bml_method =bml_method
        self.scales=scales
                     
        print(f"Mutual Information Calculator is :{mi_calculator}")
        #if mi_calculator == "kl":
        self.mi_calculator = torch.nn.KLDivLoss()
        #elif mi_calculator == "w":
        #self.mi_calculator = distance.SinkhornDistance(device=device).to(device)
                     
        self.temperature =temperature
                     
    def criterion(self,out_dict,y):
        logging.info("Entering criterion method...")
        return_losses=[]
        p_y_given_z=out_dict['p_y_given_z']
        p_y_given_f1_f2_f3_f4=out_dict['p_y_given_f_all']
        p_y_given_f1_fn_list=out_dict['p_y_given_f1_fn_list']

        # CE loss
        loss_fn = nn.CrossEntropyLoss()
        ce_loss = loss_fn(out_dict['p_y_given_z'], y)
        logging.info(f"Cross-Entropy Loss calculated: {ce_loss.item()}")

        # Debugging: Print shapes of inputs
        print(f"p_y_given_z shape: {p_y_given_z.shape}")
        print(f"p_y_given_f1_f2_f3_f4 shape: {p_y_given_f1_f2_f3_f4.shape}")


        #Global Information Loss
        if self.gil_loss:
            ce_loss+=loss_fn(p_y_given_f1_f2_f3_f4, y)
            print("Calculating global mutual information loss...")
            try:
                global_mi_loss = self.mi_calculator(self.softmax(p_y_given_f1_f2_f3_f4.detach() / self.temperature).log(),
                                                self.softmax(p_y_given_z / self.temperature))
                elapsed_time = time.time() - start_time
                logging.info(f"Global MI Loss calculated in {elapsed_time:.2f} seconds.")
            except Exception as e:
                print("Error calculating global MI Loss:", str(e))
                global_mi_loss = 0 
            

        # # for visulization
        # try:
        #     p_y_given_fi=out_dict['p_y_given_f_i']
        #     model_size=len(p_y_given_fi)
        #     for out_v in p_y_given_fi:
        #         ce_loss = ce_loss + 1/model_size*loss_fn(out_v, y)
        # except:
        #     print("no p_y_given_f_i")

        # Local Information Loss
        if self.lil_loss:
            local_loss = 0
            if self.method == 'distance':
                for i in range(len(p_y_given_f1_fn_list)):
                    for j in range(i+1,len(p_y_given_f1_fn_list)):
                        print(f"Calculating local MI between index {i} and {j}...")
                        start_time = time.time()
                        try:
                            local_loss = local_loss+self.mi_calculator(self.softmax(p_y_given_f1_fn_list[i] / self.temperature).log(),
                                                    self.softmax(p_y_given_f1_fn_list[j] / self.temperature))
                            elapsed_time = time.time() - start_time
                            logging.info(f"Local MI calculated in {elapsed_time:.2f} seconds.")
                        except Exception as e:
                            logging.error(f"Error calculating local MI between {i} and {j}: " + str(e))
                            local_loss += 0  # Fallback to 0 loss if there's an error
                        

                #local_loss=1-local_loss
            elif self.method == 'mi':
                # local MI loss
                p_y_given_f1_f2_f3_f4_soft = self.softmax(p_y_given_f1_f2_f3_f4.detach() / self.temperature)

                for out_v in p_y_given_f1_fn_list:
                    local_loss = local_loss + self.mi_calculator(p_y_given_f1_f2_f3_f4_soft.log(),
                                                     self.softmax(out_v / self.temperature))
                    ce_loss = ce_loss + loss_fn(out_v, y)
                # ce_loss = ce_loss + 0.25 * loss_fn(p_y_given_f1_fn_list[i], y)
                local_loss = torch.exp(-local_loss)
        return_losses.append(ce_loss)

        if self.gil_loss:
            return_losses.append(global_mi_loss)
        if self.lil_loss:
            return_losses.append(local_loss)
        logging.info(f"Returning losses: {return_losses}")
        return return_losses
    def balance_mult_loss(self,losses):
        if self.bml_method == 'auto':
            # Automatic Weighted Loss
            loss =self.balance_loss(losses)

        elif self.bml_method == 'hyper':
            # hyper-parameter
            loss = 0
            for i, l in enumerate(losses):
                loss = loss+l*self.scales[i]
        else:
            loss=sum(losses)
        return loss
