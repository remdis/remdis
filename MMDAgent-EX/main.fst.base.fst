# sub FST to change base motion at certain time interval

# base motion change interval in seconds
${base_duration}=16

${basemotionid}=0

0 LOOP:
   # set initial timer
   <eps> TIMER_START|basechange|${base_duration}

# change base motion to next motion when timer reaches end
LOOP BMCHANGE:
   TIMER_EVENT_STOP|basechange <eps>
BMCHANGE BMEND:
   ${basemotionid}==0 MOTION_CHANGE|0|base|asset/base/wait_b.vmd ${basemotionid}=1
BMCHANGE BMEND:
   ${basemotionid}==1 MOTION_CHANGE|0|base|asset/base/wait_moving.vmd ${basemotionid}=2
BMCHANGE BMEND:
   ${basemotionid}==2 MOTION_CHANGE|0|base|asset/base/wait.vmd ${basemotionid}=0
BMEND LOOP:
   # set the new timer
   <eps> TIMER_START|basechange|${base_duration}
