#!/usr/bin/env python 

# Standard dependencies
import sys
import os
import math
import rospy
import numpy as np
import tf
import tf2_ros
import tf_conversions

from nav_msgs.msg import Odometry
from geometry_msgs.msg import PoseWithCovarianceStamped, TransformStamped
from tf.transformations import quaternion_from_euler, euler_from_quaternion
from geometry_msgs.msg import Pose, PoseArray, Quaternion

class auv_pf():
    def __init__(self):
        # Read map frame id
        param = rospy.search_param("map_frame")
        self.map_frame = rospy.get_param(param)
        # Read odometry subscription topic
        param = rospy.search_param("odometry_topic")
        self.odom = rospy.get_param(param)
        # Read particle filter publisher topic
        param = rospy.search_param("particle_poses_topic")
        self.pf_top = rospy.get_param(param)        

        # Read particle count 
        param = rospy.search_param("particle_count")
        self.pc = rospy.get_param(param)
        # Read motion covariance values (and convert to float list) 
        param = rospy.search_param("motion_covariance")
        cov_string = rospy.get_param(param)
        cov_string = cov_string.replace('[','')
        cov_string = cov_string.replace(']','')
        cov_list = list(cov_string.split(", "))
        self.cov = list(map(float, cov_list))

        # Initialize callback variables
        self.pred_odom = None
        
        # Initialize class variables
        self.time = None
        self.old_time = None

        # Establish subscription to odometry message
        rospy.Subscriber(self.odom, Odometry, self.odom_callback)
        rospy.sleep(0.5) # CAN ADD DURATION INSTEAD?

        # Initialize array of particle states | # particles x 4 [x, y, theta_z, weight]
        self.particles = np.zeros((self.pc, 4))
        self.particles[:,3] = np.ones((self.pc,))
        
        # Initialize particle poses publisher
        self.pf_pub = rospy.Publisher(self.pf_top, PoseArray, queue_size=10)
        self.pos_ = PoseArray()
        self.pos_.header.frame_id = self.map_frame
    
    def odom_callback(self,msg):
        self.pred_odom = msg
        self.time = self.pred_odom.header.stamp.secs + self.pred_odom.header.stamp.nsecs*10**-9 
        if self.old_time and self.time > self.old_time:
            self.predict()
            self.pub_()
        self.old_time = self.time

    ##### Primary particle filter functions #####
    # def run_pf(self):
    #     if self.pred_odom != None:
    #         self.time = self.pred_odom.header.stamp.secs + self.pred_odom.header.stamp.nsecs*10**-9 
    #         if self.old_time and self.time > self.old_time:
    #             self.predict()
    #             # Publish
    #             self.pub_()
    #         self.old_time = self.time
        

    def predict(self):
        # Adding gaussian noice
        pf_noice =  self.gaussian_noise()
        # Unpack odometry message
        xv = self.pred_odom.twist.twist.linear.x
        yv = self.pred_odom.twist.twist.linear.y
        yaw_v = self.pred_odom.twist.twist.angular.z
        vel = np.sqrt(np.power(xv,2) + np.power(yv,2))
        # Update particles pose estimate
        dt = self.time - self.old_time
        # print('dt: ', dt)
        # print('xv: ', xv)
        # print('yv: ', yv)
        # print('yaw_v: ', yaw_v)
        # self.particles[:,0] += pf_noice[:,0] + xv*dt*np.cos(self.particles[:,2]) # + yv*dt*np.sin(self.particles[:,2])
        # self.particles[:,1] += pf_noice[:,1] + xv*dt*np.sin(self.particles[:,2]) # + yv*dt*np.cos(self.particles[:,2])
        # self.particles[:,0] += pf_noice[:,0] + xv*dt
        # self.particles[:,1] += pf_noice[:,1] + yv*dt
        self.particles[:,0] += pf_noice[:,0] + vel * dt * np.cos(self.particles[:,2])
        self.particles[:,1] += pf_noice[:,1] + vel * dt * np.sin(self.particles[:,2])
        self.particles[:,2] += pf_noice[:,2] + yaw_v*dt
        # Force angles to be on range [-pi, pi]
        self.particles[:,2] = np.remainder(self.particles[:,2]+np.pi,2*np.pi)-np.pi
  
  
    # Function to assign gaussian noise from diagonalcovariance matrix
    def gaussian_noise(self):
        cov_ = np.zeros((3,3))
        cov_[0,0] = self.cov[0]
        cov_[1,1] = self.cov[1]
        cov_[2,2] = self.cov[2]
        var = np.diagonal(cov_)
        return np.sqrt(var)*np.random.randn(self.pc, 3)

    def pub_(self):
        self.pos_.poses = []
        for i in range(self.pc):
            pt = Pose()
            pt.position.x = self.particles[i,0]
            pt.position.y = self.particles[i,1]
            pt.position.z = self.pred_odom.pose.pose.position.z

            yaw = self.particles[i,2]
            q = quaternion_from_euler(0,0,yaw)
            pt.orientation = Quaternion(*q)
            self.pos_.poses.append(pt)
        # Publish 
        # self.pos_.header.stamp = self.time
        self.pf_pub.publish(self.pos_)



def main():
    # Initialize ROS node
    rospy.init_node('auv_pf', anonymous=True)
    rospy.loginfo("Successful initilization of node")
    # Create particle filter class
    pf = auv_pf()
    rospy.loginfo("Particle filter class successfully created")
    # while not rospy.is_shutdown():
    #     # Run particle filter
    #     pf.run_pf()
    rospy.spin()

if __name__ == '__main__':
    main()