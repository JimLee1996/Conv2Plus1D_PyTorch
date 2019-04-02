# Conv(2+1)D PyTorch

PyTorch implementation of fractored convolution in paper, **A Closer Look at Spatiotemporal Convolutions for Action Recognition**. [[link](https://arxiv.org/abs/1711.11248)]

## Usage

```python
from conv2plus1d import FactorizedConv3d
```

`FactorizedConv3d` functions like `torch.nn.Conv3d` and has the same APIs.

## Example

See example code in [`d2plus1d.py`](d2plus1d.py), DenseNet with Conv(2+1)D in `block 3, 4`. Also refer to a module test in [`conv2plus1d.py`](conv2plus1d.py).

## Credits

- The [torchsummary](https://github.com/sksq96/pytorch-summary) is used to test this module. I've modified it with PyTorch 1.0 flavor.
