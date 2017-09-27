# *****************************************************************************
# Example Unity Connection and DQN Training Script for Playing Unity Games
#
# Use with 2D Wall Pong Game
# Use Python 2.7. (NOT tested using Python 3!)
# Tested on CPU Macbook pro; using Keras with tensorflow backend
# Recommend using a virtual env
#
# 1. In Terminal, activate virtual env, with Python 2.7, tensorflow and keras installed
# 2. run this script
# 3. start unity game and click 'connect' (either in unity or as a stand-alone app)
# 4. Watch... and watch... and watch... eventually AI success
#
# By Michael Richardson (michael.j.richardson@mq.edu.au)
# June 2017
# 
# *****************************************************************************

# **************************************************************************
# Import Python Packages and Libraries
import socket
import os
import time
import numpy as np

# **************************************************************************
# Import DDQN_Agent from Agent
from Agent import DDQN_Agent as unityAgent

# **************************************************************************
# Initialize DDQL training and (s, a) state parameters
num_episods = 2000	# number of episodes used for training
state_size = 5		# set environment state size (wallPong: ball x, ball y, ball x velocity, ball y velocity, paddle y)
action_size = 4		# set number of actions possible (wallPong: 0=do nothing; 1=up; 2=down)
reply_size = 32 	# size of action replay minibatch
targ_update = 1000	# specifies when the target model is updated, i.e., every n frames
pframe = 4			# specifies frame downsample factor (i.e., process action only every n frames)

# **************************************************************************
# Initiate agent and agent variables
# unityAgent=(state_size, action_size, gamma, learning_rate, epsilon, epsilon_decay, epsilon_min, epsilon_delay, memory_length)
agent = unityAgent(state_size, action_size, .99, .001, 1.0, .9999, .05, 25000, 200000)
newstate = np.reshape([0,0,0,0,0], [1, state_size])		# Initialize new game state cache (array)
oldstate = np.reshape([0,0,0,0,0], [1, state_size])		# Initialize old game state cache (array)
#agent.load("./aWData_20170728_131503/aw_ep213.h5") 		# If pre-loading network weights, do that here

# **************************************************************************
# Initialize weights directory (folder) and pre-filename string for saving agent's NN weights files
timestr = time.strftime("%Y%m%d_%H%M%S")
wfiledir = "./aWData_" + timestr
if not os.path.exists(wfiledir):
    os.makedirs(wfiledir)

# **************************************************************************
# Initialize episode/training data file (for post-training analysis)
episodeDfname = wfiledir + "/episodeData_" + timestr + ".csv"
episodeDFile = open(episodeDfname, "w")
episodeDFile.write("Episode, Frame, Epsilon, EpisodeReward\n")

# **************************************************************************
# Save agent parameters
aDfname = wfiledir + "/agentParameters" + timestr + ".txt"		
agent.save_agent_parameters(aDfname)

# **************************************************************************
# Save training parameters
tDfname = wfiledir + "/trainingParameters" + timestr + ".txt"
tDfile = open(tDfname, "w")
tDfile.write("Number of episodes: " + str(num_episods) + "\n")
tDfile.write("State size: " + str(state_size) + "\n")
tDfile.write("Action size: " + str(action_size) + "\n")
tDfile.write("Reply size: " + str(reply_size) + "\n")
tDfile.write("Frame downsample factor: " + str(pframe) + "\n")
tDfile.close()

# **************************************************************************
# Create a TCP/IP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Initialize TCP socket
server_address = ('localhost', 10000)					 # Set TCP server address
sock.bind(server_address)								 # Bind the TCP socket address to the port
print('starting up on %s port %s' % server_address)		 # Print TCP socket info to terminal
sock.listen(1)											 # Listen for incoming connections


# **************************************************************************
# Main While loop to run DDQN RL process
# First, waits for clinet connection from unity game
# Once clinet connects, 
while True:
	# Wait for a connection
	print('waiting for a connection')
	connection, client_address = sock.accept()

	try:
		# Connection from unity client made
		print('connection from', client_address)

		# Initialize training and episode varibles
		fcount = 1			# frame (in data) count
		episode = 1			# episode count
		action = 0			# agent action
		reward = 0			# reward received for action made by agent
		episode_reward = 0	# total reward score for episode

		# send initial rest and action message to game to start game
		# wallPong game expects two integer values (rest, action)
		# to rest game, reset = 1, otherwise set reset=0	
		connection.sendall("1 0 ")
        
		# reset initial (default) message string
		message = "0 {} ".format(action)

		# Complete training
		while episode < num_episods+1:

			# Check for new game data
			# for wallPong incomming game data is a string of 5 floats and 2 integers. 
			# The data order is as follows: ball_x, ball_y, ball_x_velocity, ball_y_velocity, paddle_y, reward, done
			data = connection.recv(33)
			#print('received: {}'.format(data))

			# Process game data if received
			if data:

            	# Process new game data by first split data into a float array.
				data_int = map(float, data.split())	

				# Extract and process new game state data (ball_x, ball_y, ball_x_velocity, ball_y_velocity, paddle_y)
				# NOTE 1:   x and y positions sent from unity on normlazied range 0 to 1, where:
				#			left wall  is at x = 0; dotted line (paddle) is at x = 1;
				#			bottom wall is at y = 0; and top wall is at y = 1
				# NOTE 2:   x and y velocities sent from unity on normlazied range 0 to 2, where 1 = 0 velocity, 
				#			hence a -1 is added to vel;ocities to rescale them to -1 to 1 (i.e., normalized neg to pos velocities)
				# NOTE 3:	newstate is reshaped, as this is the shape that Keras NN expects the state data to be in
				new_state_data = data_int[0:5]
				newstate = [new_state_data[0],new_state_data[1]-1,new_state_data[2],new_state_data[3]-1,new_state_data[4]]
				newstate = np.reshape(newstate, [1, state_size])

				# Extract reward (last value in game data) and whether current game episdoe is done (over) or not
				# NOTE 4: rewards sent as positive intergers, which are processed here as: 0=-1, 1=0, 2=1
				reward = reward + data_int[5]-1
				done = data_int[6]

				# If end of game episode, process replay memeory with done at end (i.e., 1)
				# Output current episdoe data to terminal window
				if done:
					episode_reward = episode_reward+reward 					# update episode reward
					agent.remember(oldstate, action, reward, newstate, 1)	# add new dtata to agent replay memory
					agent.replay(reply_size, fcount) 						# process action replay minibatch

					# Print and save current episode data			
					print("Episode: {}, Frame Count: {},  Epsilon: {},  Total Episode Reward: {}".format(episode, fcount, agent.epsilon, episode_reward))
					episodeDFile.write(str(episode) + "," + str(fcount) + "," + str(agent.epsilon) + "," + str(episode_reward) + "\n")

					# Save current weights for agent' sNN model
					afname = wfiledir + "/aw_ep" + str(episode) + ".h5"		# set filename for current model weights for agent
					agent.save(afname)										# save cuurent model (NN) weights to file for agent

					episode = episode+1										# increase episode count
					episode_reward = 0										# rest total reward for episode
					reward = 0												# rest current reward
					action = 0												# set action to 0
					message = "1 0 "										# set new outgoing message, with game rest=1 and action=0
				
				else:
					# Process every n-frames or if game is done (over)
					if fcount % pframe == 0:
						episode_reward = episode_reward+reward 					# update episode reward
						agent.remember(oldstate, action, reward, newstate, 0)	# add new dtata to agent replay memory
						agent.replay(reply_size, fcount)						# process action replay minibatch
						action = agent.act(newstate)							# determine new action from new state data
						message = "0 {} ".format(action)						# set new outgoing message with game action
						oldstate = newstate 									# save new state data as old state data
						reward = 0												# rest current reward
				
				# send current rest and action message to unity game	
				connection.sendall(message)

				# update target NN model after n-frames
				if fcount % targ_update == 0:
					agent.update_target_model()								# update agent's target model (NN)

				# update frame count
				fcount = fcount+1

			else:
				# break if no more data comming in from client
			    print("Data stream from client {} stopped".format(client_address))
			    break

	finally:
		# Clean up the connection
		connection.close()

		#close edisode data file
		episodeDFile.close()

		# earse (delete, clear) replay memory array
		agent.erase_replay_memory()

		# Close TCP connnection and socket and break to exit
		print("Client connection closed and reply memory earsed")
		print("Closing TCP socket...")
		sock.close()
		print("Training Over\n\n")
		break
