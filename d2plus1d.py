import math
from collections import OrderedDict

import torch
import torch.nn as nn
import torch.nn.functional as F

from conv2plus1d import FactorizedConv3d


class _DenseLayer(nn.Sequential):
    def __init__(self, num_input_features, growth_rate, bn_size, drop_rate):
        super(_DenseLayer, self).__init__()
        self.add_module('norm1', nn.BatchNorm3d(num_input_features))
        self.add_module('relu1', nn.ReLU(inplace=True))
        self.add_module(
            'conv1',
            nn.Conv3d(
                num_input_features,
                bn_size * growth_rate,
                kernel_size=1,
                stride=1,
                bias=False
            )
        )
        self.add_module('norm2', nn.BatchNorm3d(bn_size * growth_rate))
        self.add_module('relu2', nn.ReLU(inplace=True))
        self.add_module(
            'conv2',
            nn.Conv3d(
                bn_size * growth_rate,
                growth_rate,
                kernel_size=3,
                stride=1,
                padding=1,
                bias=False
            )
        )
        self.drop_rate = drop_rate

    def forward(self, x):
        new_features = super(_DenseLayer, self).forward(x)
        if self.drop_rate > 0:
            new_features = F.dropout(
                new_features, p=self.drop_rate, training=self.training
            )
        return torch.cat([x, new_features], 1)


class _DenseBlock(nn.Sequential):
    def __init__(
        self, num_layers, num_input_features, bn_size, growth_rate, drop_rate
    ):
        super(_DenseBlock, self).__init__()
        for i in range(num_layers):
            layer = _DenseLayer(
                num_input_features + i * growth_rate, growth_rate, bn_size,
                drop_rate
            )
            self.add_module('denselayer%d' % (i + 1), layer)


class _FactorizedDenseLayer(nn.Sequential):
    def __init__(
        self, num_input_features, growth_rate, bn_size, drop_rate, factor_rate
    ):
        super(_FactorizedDenseLayer, self).__init__()
        self.add_module('norm1', nn.BatchNorm3d(num_input_features))
        self.add_module('relu1', nn.ReLU(inplace=True))
        self.add_module(
            'conv1',
            nn.Conv3d(
                num_input_features,
                bn_size * growth_rate,
                kernel_size=1,
                stride=1,
                bias=False
            )
        )
        self.add_module('norm2', nn.BatchNorm3d(bn_size * growth_rate))
        self.add_module('relu2', nn.ReLU(inplace=True))
        self.add_module(
            'conv2',
            FactorizedConv3d(
                bn_size * growth_rate,
                growth_rate,
                kernel_size=3,
                stride=1,
                padding=1,
                bias=False,
                factor_rate=factor_rate
            )
        )
        self.drop_rate = drop_rate

    def forward(self, x):
        new_features = super(_FactorizedDenseLayer, self).forward(x)
        if self.drop_rate > 0:
            new_features = F.dropout(
                new_features, p=self.drop_rate, training=self.train
            )
        return torch.cat([x, new_features], 1)


class _FactorizedDenseBlock(nn.Sequential):
    def __init__(
        self, num_layers, num_input_features, bn_size, growth_rate, drop_rate,
        factor_rate
    ):
        super(_FactorizedDenseBlock, self).__init__()
        for i in range(num_layers):
            layer = _FactorizedDenseLayer(
                num_input_features + i * growth_rate, growth_rate, bn_size,
                drop_rate, factor_rate
            )
            self.add_module('factorized_denselayer%d' % (i + 1), layer)


class _Transition(nn.Sequential):
    def __init__(self, num_input_features, num_output_features):
        super(_Transition, self).__init__()
        self.add_module('norm', nn.BatchNorm3d(num_input_features))
        self.add_module('relu', nn.ReLU(inplace=True))
        self.add_module(
            'conv',
            nn.Conv3d(
                num_input_features,
                num_output_features,
                kernel_size=1,
                stride=1,
                bias=False
            )
        )
        self.add_module('pool', nn.AvgPool3d(kernel_size=2, stride=2))


class Dense2Plus1DNet(nn.Module):
    r"""Densely connected network with (2+1) convolutional kernel
    Args:
        growth_rate (int) - how many filters to add each layer (k in paper)
        block_config (list of 4 ints) - how many layers in each pooling block
        num_init_features (int) - the number of filters to learn in the first convolution layer
        bn_size (int) - multiplicative factor for number of bottle neck layers
          (i.e. bn_size * k features in the bottleneck layer)
        drop_rate (float) - dropout rate after each dense layer
        factor_rate (float) - scale the number of parameters in FactorizedConv3d
        num_classes (int) - number of classification classes
    """

    def __init__(
        self,
        sample_duration,
        sample_size,
        growth_rate=32,
        block_config=(6, 12, 24, 16),
        num_init_features=64,
        bn_size=4,
        drop_rate=0,
        factor_rate=1.0,
        num_classes=1000
    ):

        super(Dense2Plus1DNet, self).__init__()

        self.sample_size = sample_size
        self.sample_duration = sample_duration

        # First convolution
        self.features = nn.Sequential(
            OrderedDict(
                [
                    (
                        'conv0',
                        nn.Conv3d(
                            3,
                            num_init_features,
                            kernel_size=7,
                            stride=(1, 2, 2),
                            padding=(3, 3, 3),
                            bias=False
                        )
                    ),
                    ('norm0', nn.BatchNorm3d(num_init_features)),
                    ('relu0', nn.ReLU(inplace=True)),
                    ('pool0', nn.MaxPool3d(kernel_size=3, stride=2, padding=1)),
                ]
            )
        )

        # Each denseblock
        num_features = num_init_features
        for i, num_layers in enumerate(block_config):
            if i == 0:
                block = _DenseBlock(
                    num_layers=num_layers,
                    num_input_features=num_features,
                    bn_size=bn_size,
                    growth_rate=growth_rate,
                    drop_rate=drop_rate
                )
                self.features.add_module('denseblock%d' % (i + 1), block)
            else:
                block = _FactorizedDenseBlock(
                    num_layers=num_layers,
                    num_input_features=num_features,
                    bn_size=bn_size,
                    growth_rate=growth_rate,
                    drop_rate=drop_rate,
                    factor_rate=factor_rate
                )
                self.features.add_module(
                    'factorized_denseblock%d' % (i + 1), block
                )
            num_features = num_features + num_layers * growth_rate
            if i != len(block_config) - 1:
                trans = _Transition(
                    num_input_features=num_features,
                    num_output_features=num_features // 2
                )
                self.features.add_module('transition%d' % (i + 1), trans)
                num_features = num_features // 2

        # Final batch norm
        self.features.add_module('norm5', nn.BatchNorm3d(num_features))

        # Official init from torch repo.
        for m in self.modules():
            if isinstance(m, nn.Conv3d):
                nn.init.kaiming_normal_(m.weight)
            elif isinstance(m, nn.BatchNorm3d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.Linear):
                nn.init.constant_(m.bias, 0)
            # perform self-defined init.
            elif isinstance(m, FactorizedConv3d):
                m.param_init()

        # Linear layer
        self.classifier = nn.Linear(num_features, num_classes)

    def forward(self, x):
        features = self.features(x)
        out = F.relu(features, inplace=True)

        torch.nn.AdaptiveAvgPool3d

        out = F.adaptive_avg_pool3d(out, (1, 1, 1)).view(features.size(0), -1)

        out = self.classifier(out)
        return out


def get_finetune_params(model, finetune_module_names=[]):
    if not finetune_module_names:
        return model.parameters()

    for param in model.parameters():
        param.requires_grad = False

    finetune_module_names.append('norm5')
    finetune_module_names.append('classifier')

    for name, param in model.named_parameters():
        for ft_module in finetune_module_names:
            if ft_module in name:
                param.requires_grad = True
                break

    return model.parameters()


def d2plus1d121(**kwargs):
    model = Dense2Plus1DNet(
        num_init_features=64,
        growth_rate=32,
        block_config=(6, 12, 24, 16),
        **kwargs
    )
    return model


if __name__ == '__main__':
    model = d2plus1d121(
        sample_duration=16, sample_size=112, factor_rate=0.5, num_classes=2
    )
    for m in model.modules():
        if isinstance(m, FactorizedConv3d):
            print(m)

    for name, param in model.named_parameters():
        print(name)

    from torchsummary import summary

    summary(model, (3, 16, 112, 112))
