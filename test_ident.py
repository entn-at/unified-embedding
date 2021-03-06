import numpy as np
import caffe
print "Caffe successfully imported!"
import scipy.io.wavfile
import re
import os.path

wav_list='/scratch_net/biwidl09/hmahdi/VoxCeleb/Identification_split.txt'
base_address='/scratch_net/biwidl09/hmahdi/VoxCeleb/voxceleb1_wav/'
pre_emphasis = 0.97
frame_size = 0.025
frame_stride = 0.01
NFFT = 512
BATCH_SIZE=50
train_set=[]
train_label=[]
validation_set=[]
validation_label=[]
test_set=[]
test_label=[]
spectrogram_batch=np.empty([BATCH_SIZE,1,300,257],dtype=float) # np.int((NFFT+1)/2)
label_batch=np.empty([BATCH_SIZE,1,1,1],dtype=float)
number_of_crops=50

def crop_inference(batch_index):
	for i in range(0,BATCH_SIZE):
		sample_index=batch_index*BATCH_SIZE+i
		file_name=test_set[sample_index] # Every sample within the batch is chosen at random
		sample_rate, signal = scipy.io.wavfile.read(file_name)  #
		extendedSignal=np.append(signal,signal)
		beginning=int((len(signal))*np.random.random_sample())
		signal = extendedSignal[beginning:beginning+48241]  # Number of samples plus one because we need to apply pre-emphasis filter with receptive field of two
		if (np.int(np.random.random_sample()*2)==1):
			signal= signal[::-1]
		signal=signal-np.mean(signal)
		emphasized_signal = np.append(signal[0], signal[1:] - pre_emphasis * signal[:-1])

		frame_length, frame_step = frame_size * sample_rate, frame_stride * sample_rate  # Convert from seconds to samples
		signal_length = len(emphasized_signal)
		frame_length = int(round(frame_length))
		frame_step = int(round(frame_step))
		num_frames = int(np.ceil(float(np.abs(signal_length - frame_length)) / frame_step))  # Make sure that we have at least 1 frame

		pad_signal_length = num_frames * frame_step + frame_length
		z = np.zeros((pad_signal_length - signal_length))
		pad_signal = np.append(emphasized_signal, z) # Pad Signal to make sure that all frames have equal number of samples without truncating any samples from the original signal

		indices = np.tile(np.arange(0, frame_length), (num_frames, 1)) + np.tile(np.arange(0, num_frames * frame_step, frame_step), (frame_length, 1)).T
		frames = pad_signal[indices.astype(np.int32, copy=False)]

		frames *= np.hamming(frame_length)
		mag_frames = np.absolute(np.fft.rfft(frames, NFFT))  # Magnitude of the FFT

		label_batch[i,0,0,0]=test_label[sample_index]
		spectrogram_batch[i,0,:,:]= (mag_frames - mag_frames.mean(axis=0)) / mag_frames.std(axis=0)


def test_accuracy(net):
	
	test_set_size=len(test_set)
	print("Start of testing process on %d samples" % (test_set_size))
	top1Accuracy=0
	top5Accuracy=0
	for i in range(0,test_set_size/BATCH_SIZE):
		for j in range(0,number_of_crops):        
			crop_inference(i)
			net.blobs['data'].data[...] =spectrogram_batch
			net.blobs['label'].data[...]  =label_batch
			net.forward()
			if j==0:
				batch_pool_average=net.blobs['res4_3p'].data
			else:
				batch_pool_average=batch_pool_average+net.blobs['res4_3p'].data
		batch_pool_average=batch_pool_average/number_of_crops
		net.blobs['res4_3p'].data[...] = batch_pool_average
		net.forward(start='fc5')#, end='fc7')
		top1Accuracy=top1Accuracy+net.blobs['top1Accuracy'].data
		top5Accuracy=top5Accuracy+net.blobs['top5Accuracy'].data
		print("Batch #%d of testing is evaluated"% (i))
	top1Accuracy=top1Accuracy*BATCH_SIZE/test_set_size
	top5Accuracy=top5Accuracy*BATCH_SIZE/test_set_size
	print("The top1 accuracy on test set is %.4f" % (top1Accuracy))
	print("The top5 accuracy on test set is %.4f" % (top5Accuracy))


if __name__ == '__main__':

	allocated_GPU= int(os.environ['SGE_GPU'])
	print("The training will be executed on GPU #%d" % (allocated_GPU))
	caffe.set_device(allocated_GPU)
	caffe.set_mode_gpu()
	net_weights='result/LM_512D_30_iter_61600.caffemodel'
	net_prototxt='prototxt/LogisticMargin.prototxt'
	net = caffe.Net(net_prototxt,net_weights,caffe.TEST)
	print("The network will be initialized with coefficients from %s" % (net_weights))

	input_file = open(wav_list,'r')
	identity=0 
	split_index=1
	for line in input_file:
		parsed_line=re.split(r'[ \n]+', line)	
		utterance_address=base_address+parsed_line[1]
		prev_split_index=split_index
		split_index=int(parsed_line[0])
		if (prev_split_index>split_index):
			identity=identity+1
		if (os.path.isfile(utterance_address)==False): # The file does not exist
			continue
		elif (split_index==1):
			train_set.append(utterance_address)
			train_label.append(identity)
		elif (split_index==2):
			validation_set.append(utterance_address)
			validation_label.append(identity)
		elif (split_index==3):
			test_set.append(utterance_address)
			test_label.append(identity)
	print("The size of training set: %d" % (len(train_set))) 
	print("The size of validation set: %d" % (len(validation_set))) 
	print("The size of test set: %d" % (len(test_set))) 
	print("Number of identities: %d" % (identity+1))
	test_accuracy(net)
