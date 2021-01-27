from distutils.version import LooseVersion
from functools import partial

import pytest
import torch
from sklearn.metrics import roc_auc_score as sk_roc_auc_score

from pytorch_lightning.metrics.classification.auroc import AUROC
from pytorch_lightning.metrics.functional.auroc import auroc
from tests.metrics.classification.inputs import (
    _binary_prob_inputs,
    _multiclass_prob_inputs,
    _multidim_multiclass_prob_inputs,
    _multilabel_multidim_prob_inputs,
    _multilabel_prob_inputs,
)
from tests.metrics.utils import MetricTester, NUM_CLASSES

torch.manual_seed(42)


def _binary_prob_sk_metric(preds, target, num_classes, average='macro', max_fpr=None, multi_class='ovr'):
    sk_preds = preds.view(-1).numpy()
    sk_target = target.view(-1).numpy()
    return sk_roc_auc_score(y_true=sk_target, y_score=sk_preds, average=average, max_fpr=max_fpr)


def _multiclass_prob_sk_metric(preds, target, num_classes, average='macro', max_fpr=None, multi_class='ovr'):
    sk_preds = preds.reshape(-1, num_classes).numpy()
    sk_target = target.view(-1).numpy()
    return sk_roc_auc_score(
        y_true=sk_target,
        y_score=sk_preds,
        average=average,
        max_fpr=max_fpr,
        multi_class=multi_class
    )


def _multidim_multiclass_prob_sk_metric(preds, target, num_classes, average='macro', max_fpr=None, multi_class='ovr'):
    sk_preds = preds.transpose(0, 1).reshape(num_classes, -1).transpose(0, 1).numpy()
    sk_target = target.view(-1).numpy()
    return sk_roc_auc_score(
        y_true=sk_target,
        y_score=sk_preds,
        average=average,
        max_fpr=max_fpr,
        multi_class=multi_class
    )


def _multilabel_prob_sk_metric(preds, target, num_classes, average='macro', max_fpr=None, multi_class='ovr'):
    sk_preds = preds.reshape(-1, num_classes).numpy()
    sk_target = target.reshape(-1, num_classes).numpy()
    return sk_roc_auc_score(
        y_true=sk_target,
        y_score=sk_preds,
        average=average,
        max_fpr=max_fpr,
        multi_class=multi_class
    )


def _multilabel_multidim_prob_sk_metric(preds, target, num_classes, average='macro', max_fpr=None, multi_class='ovr'):
    sk_preds = preds.transpose(0, 1).reshape(num_classes, -1).transpose(0, 1).numpy()
    sk_target = target.transpose(0, 1).reshape(num_classes, -1).transpose(0, 1).numpy()
    return sk_roc_auc_score(
        y_true=sk_target,
        y_score=sk_preds,
        average=average,
        max_fpr=max_fpr,
        multi_class=multi_class
    )


@pytest.mark.parametrize("preds, target, sk_metric, num_classes", [
    (_binary_prob_inputs.preds, _binary_prob_inputs.target, _binary_prob_sk_metric, 1),
    (
        _multiclass_prob_inputs.preds,
        _multiclass_prob_inputs.target,
        _multiclass_prob_sk_metric,
        NUM_CLASSES
    ),
    (
        _multidim_multiclass_prob_inputs.preds,
        _multidim_multiclass_prob_inputs.target,
        _multidim_multiclass_prob_sk_metric,
        NUM_CLASSES
    ),
    (
        _multilabel_prob_inputs.preds,
        _multilabel_prob_inputs.target,
        _multilabel_prob_sk_metric,
        NUM_CLASSES
    ),
    (
        _multilabel_multidim_prob_inputs.preds,
        _multilabel_multidim_prob_inputs.target,
        _multilabel_multidim_prob_sk_metric,
        NUM_CLASSES
    )
])
@pytest.mark.parametrize("average", ['macro', 'weighted'])
@pytest.mark.parametrize("max_fpr", [None, 0.8, 0.5])
class TestAUROC(MetricTester):
    @pytest.mark.parametrize("ddp", [True, False])
    @pytest.mark.parametrize("dist_sync_on_step", [True, False])
    def test_auroc(self, preds, target, sk_metric, num_classes, average, max_fpr, ddp, dist_sync_on_step):
        # max_fpr different from None is not support in multi class
        if max_fpr is not None and num_classes != 1:
            pytest.skip('max_fpr parameter not support for multi class or multi label')

        # max_fpr only supported for torch v1.6 or higher
        if max_fpr is not None and LooseVersion(torch.__version__) < LooseVersion('1.6.0'):
            pytest.skip('requires torch v1.6 or higher to test max_fpr argument')

        self.run_class_metric_test(
            ddp=ddp,
            preds=preds,
            target=target,
            metric_class=AUROC,
            sk_metric=partial(sk_metric, num_classes=num_classes, average=average, max_fpr=max_fpr),
            dist_sync_on_step=dist_sync_on_step,
            metric_args={"num_classes": num_classes,
                         "average": average,
                         "max_fpr": max_fpr},
        )

    def test_auroc_functional(self, preds, target, sk_metric, num_classes, average, max_fpr):
        # max_fpr different from None is not support in multi class
        if max_fpr is not None and num_classes != 1:
            pytest.skip('max_fpr parameter not support for multi class or multi label')

        # max_fpr only supported for torch v1.6 or higher
        if max_fpr is not None and LooseVersion(torch.__version__) < LooseVersion('1.6.0'):
            pytest.skip('requires torch v1.6 or higher to test max_fpr argument')

        self.run_functional_metric_test(
            preds,
            target,
            metric_functional=auroc,
            sk_metric=partial(sk_metric, num_classes=num_classes, average=average, max_fpr=max_fpr),
            metric_args={"num_classes": num_classes,
                         "average": average,
                         "max_fpr": max_fpr},
        )


def test_error_on_different_mode():
    """ test that an error is raised if the user pass in data of
        different modes (binary, multi-label, multi-class)
    """
    metric = AUROC()
    # pass in multi-class data
    metric.update(torch.randn(10, 5).softmax(dim=-1), torch.randint(0, 5, (10,)))
    with pytest.raises(
            ValueError,
            match=r"The mode of data.* should be constant.*"
    ):
        # pass in multi-label data
        metric.update(torch.rand(10, 5), torch.randint(0, 2, (10,5)))
