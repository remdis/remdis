# sub FST to invoke some actions periodically for animacy

# interval time in seconds to invoke an action
${shigusa_interval}=10

0 LOOP:
   # set initial timer
   <eps> TIMER_START|shigusa|${shigusa_interval}

# invoke one of the pre-defined three actions when timer reaches end
LOOP SG1:
   # set randam value to "rand"
   TIMER_EVENT_STOP|shigusa VALUE_SET|rand|0.0|8.0
   # invoke test if "rand" <= 1.0 
   VALUE_EVENT_SET|rand VALUE_EVAL|rand|LE|1.0
# in case ("rand" <= 1.0) is true, goto SHIGUSA1
SG1 SHIGUSA1  VALUE_EVENT_EVAL|rand|LE|1.0|TRUE <eps>
# in case ("rand" <= 1.0) is false, invoke test if "rand" <= 2.0 and goto SG2
SG1 SG2       VALUE_EVENT_EVAL|rand|LE|1.0|FALSE VALUE_EVAL|rand|LE|2.0
# in case ("rand" <= 2.0) is true, goto SHIGUSA2
SG2 SHIGUSA2  VALUE_EVENT_EVAL|rand|LE|2.0|TRUE <eps>
# else, goto SHIGUSA3
SG2 SHIGUSA3  VALUE_EVENT_EVAL|rand|LE|2.0|FALSE <eps>

# action 1: looking around
SHIGUSA1 SGEND:
   <eps> MOTION_ADD|0|shigusa|asset/actions/lookaround.vmd|PART|ONCE|ON|OFF
   MOTION_EVENT_ADD|0|shigusa <eps>
# action 2: touch cloth
SHIGUSA2 SGEND:
   <eps> MOTION_ADD|0|shigusa|asset/actions/touch_cloth.vmd|PART|ONCE|ON|OFF
   MOTION_EVENT_ADD|0|shigusa <eps>
# action 3: sleepy
SHIGUSA3 SGEND:
   <eps> MOTION_ADD|0|shigusa|asset/actions/sleepy.vmd|PART|ONCE|ON|OFF
   MOTION_EVENT_ADD|0|shigusa <eps>
# re-set timer for next invocation
SGEND LOOP:
   <eps> TIMER_START|shigusa|${shigusa_interval}
