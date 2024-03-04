# main fst

0 100:
    # load floor and background images
    <eps> STAGE|asset/images/floor.png,asset/images/grad1.png
    # add CG model
    <eps> MODEL_ADD|0|asset/models/uka/MS_Uka.pmd
    # add basic wait motion as a loop motion
    MODEL_EVENT_ADD|0  MOTION_ADD|0|base|asset/base/wait.vmd|FULL|LOOP|ON|OFF
    # set window frame image
    <eps> WINDOWFRAME|asset/images/frame_trad.png
    # set camera position
    <eps> CAMERA|0,18.25,0|4.5,0,0|22.4|27.0
