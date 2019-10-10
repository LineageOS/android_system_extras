#include <binder/AppOpsManager.h>

#include "appops-wrapper.h"

using namespace android;

int appops_start_op_su(int uid, const char* pkgName) {
    AppOpsManager ops;
    int mode = ops.startOpNoThrow(AppOpsManager::OP_SU, uid, String16(pkgName), false);
    if (mode == AppOpsManager::MODE_ALLOWED) {
        return 0;
    }

    return 1;
}

void appops_finish_op_su(int uid, const char* pkgName) {
    AppOpsManager* ops = new AppOpsManager();
    ops->finishOp(AppOpsManager::OP_SU, uid, String16(pkgName));
    delete ops;
}
