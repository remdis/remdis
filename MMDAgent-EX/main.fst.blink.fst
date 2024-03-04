# sub FST for periodical eye blinking

# time interval of blinking in seconds
${blink_interval}=4

0 LOOP:
   # start initial timer
   <eps> TIMER_START|blink|${blink_interval}

# invoke blink motion when the timer reaches end
LOOP LOOP:
   # start motion
   TIMER_EVENT_STOP|blink MOTION_ADD|0|blink|asset/actions/blink.vmd|PART|ONCE|ON|OFF
   # set the motion as multiplied-motion to cope with eye control of other motions
   MOTION_EVENT_ADD|0|blink MOTION_CONFIGURE|0|blink|MODE_MUL
   # re-set the timer for next invocation   
   <eps> TIMER_START|blink|${blink_interval}
